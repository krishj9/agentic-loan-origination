"""Cognito JWT authentication: JWKS validation, group-to-role mapping.

Design §4.1 / §4.3: the API validates every inbound request against the
Cognito User Pool's JWKS endpoint.  Failed authentication emits a
structured warning to the auth log group (CloudWatch) and returns 401.

Role mapping:
  cognito:groups ∋ "LoanOfficer"  →  can create applications, upload
                                      documents, and review decisions.
  cognito:groups ∋ "Operator"     →  read-only config and log inspection.
"""

import logging
import time
from collections.abc import Callable
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.core.settings import Settings, get_settings

log = logging.getLogger(__name__)

ROLE_LOAN_OFFICER = "LoanOfficer"
ROLE_OPERATOR = "Operator"

_http_bearer = HTTPBearer(auto_error=False)


# ── JWKS caching ──────────────────────────────────────────────────────────────


class _JWKSCache:
    """Thread-safe (async-safe) in-memory JWKS cache with 1-hour TTL.

    Refreshes eagerly on cache miss and retries once on unknown kid to
    handle Cognito key-rotation without requiring a service restart.
    """

    TTL_SECONDS = 3_600

    def __init__(self) -> None:
        self._keys: dict[str, object] = {}
        self._fetched_at: float = 0.0

    async def get_public_key(self, kid: str, jwks_uri: str) -> object | None:
        """Return the JWK for the given kid, refreshing if stale or missing."""
        now = time.monotonic()
        if now - self._fetched_at > self.TTL_SECONDS or not self._keys:
            await self._refresh(jwks_uri)

        key = self._keys.get(kid)
        if key is None:
            # Retry once to handle key rotation between cache fill and use
            await self._refresh(jwks_uri)
            key = self._keys.get(kid)

        return key

    async def _refresh(self, jwks_uri: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_uri)
            resp.raise_for_status()
            data = resp.json()

        self._keys = {k["kid"]: k for k in data.get("keys", [])}
        self._fetched_at = time.monotonic()
        log.info("JWKS refreshed", extra={"key_count": len(self._keys)})


_jwks_cache = _JWKSCache()


# ── Token validation ──────────────────────────────────────────────────────────


async def _validate_cognito_token(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
) -> dict[str, object]:
    """Validate a Bearer JWT against the Cognito JWKS and return its claims.

    Raises HTTPException(401) for any validation failure.  Logs a warning
    (without the token value) to aid CloudWatch auth-failure monitoring.
    """
    if credentials is None:
        log.warning("Request received without Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    token = credentials.credentials

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        log.warning("JWT header decode failed — malformed token")
        raise HTTPException(status_code=401, detail="Invalid token format.") from None

    kid = unverified_header.get("kid")
    if not kid:
        log.warning("JWT missing kid header")
        raise HTTPException(status_code=401, detail="Token missing signing key ID.") from None

    public_key = await _jwks_cache.get_public_key(kid, settings.jwks_uri)
    if public_key is None:
        log.warning("Unknown signing key", extra={"kid": kid})
        raise HTTPException(status_code=401, detail="Unknown token signing key.") from None

    try:
        claims: dict[str, object] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"verify_exp": True},
        )
    except JWTError as exc:
        log.warning("JWT validation failed", extra={"reason": str(exc)})
        raise HTTPException(status_code=401, detail="Token validation failed.") from None

    return claims


# ── Current-user representation ───────────────────────────────────────────────


class CurrentUser:
    """Holds the authenticated user's identity extracted from the JWT claims."""

    def __init__(self, sub: str, username: str, groups: list[str]) -> None:
        self.sub = sub
        self.username = username
        self.groups = groups

    @property
    def is_loan_officer(self) -> bool:
        """True when the user belongs to the LoanOfficer Cognito group."""
        return ROLE_LOAN_OFFICER in self.groups

    @property
    def is_operator(self) -> bool:
        """True when the user belongs to the Operator Cognito group."""
        return ROLE_OPERATOR in self.groups


# ── FastAPI dependency ─────────────────────────────────────────────────────────


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_http_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    """FastAPI dependency that validates the Cognito JWT.

    Resolves to a CurrentUser on success; raises 401 on any auth failure.
    Intended to be composed via require_role() for endpoint-level enforcement.
    """
    claims = await _validate_cognito_token(credentials, settings)
    raw_groups = claims.get("cognito:groups") or []
    groups: list[str] = [str(g) for g in raw_groups] if isinstance(raw_groups, list) else []
    user = CurrentUser(
        sub=str(claims.get("sub", "")),
        username=str(claims.get("cognito:username", claims.get("username", ""))),
        groups=groups,
    )
    # Bind user_id into the logging context for this request
    from backend.core.logging import set_user_id  # local import avoids cycle

    set_user_id(user.sub)
    return user


# ── Role-enforcement helpers ───────────────────────────────────────────────────


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Return a FastAPI dependency that enforces at least one of the given roles.

    Usage::

        @router.post("/applications")
        async def create(user: Annotated[CurrentUser, Depends(require_role(ROLE_LOAN_OFFICER))]):
            ...
    """

    async def _enforce(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        for role in roles:
            if role in user.groups:
                return user
        log.warning(
            "Authorization denied — insufficient role",
            extra={"required_roles": list(roles), "user_groups": user.groups},
        )
        raise HTTPException(status_code=403, detail="Insufficient permissions.")

    return _enforce


# Convenience dependency aliases used as type-annotation metadata in routes
RequireLoanOfficer = Depends(require_role(ROLE_LOAN_OFFICER))
RequireOperator = Depends(require_role(ROLE_OPERATOR))
RequireAnyRole = Depends(require_role(ROLE_LOAN_OFFICER, ROLE_OPERATOR))
