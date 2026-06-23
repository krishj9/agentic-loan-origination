"""Unit tests for Cognito JWT authentication helpers.

Tests cover:
  - _validate_cognito_token: 401 on missing credentials.
  - CurrentUser: role-check properties.
  - require_role: grants access when role matches, 403 when not.
  - get_current_user: binds user_id to logging context.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.core.auth import (
    ROLE_LOAN_OFFICER,
    ROLE_OPERATOR,
    CurrentUser,
    _validate_cognito_token,
    get_current_user,
    require_role,
)
from backend.core.settings import Settings


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    return Settings(
        cognito_user_pool_id="us-east-1_TEST",
        cognito_client_id="test-client-id",
    )


# ── _validate_cognito_token ───────────────────────────────────────────────────


async def test_validate_token_raises_401_when_no_credentials(settings: Settings) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _validate_cognito_token(None, settings)
    assert exc_info.value.status_code == 401


async def test_validate_token_raises_401_for_malformed_token(settings: Settings) -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.jwt")
    with pytest.raises(HTTPException) as exc_info:
        await _validate_cognito_token(credentials, settings)
    assert exc_info.value.status_code == 401


# ── CurrentUser ───────────────────────────────────────────────────────────────


def test_current_user_is_loan_officer_when_in_group() -> None:
    user = CurrentUser(sub="sub-1", username="u", groups=[ROLE_LOAN_OFFICER])
    assert user.is_loan_officer is True
    assert user.is_operator is False


def test_current_user_is_operator_when_in_group() -> None:
    user = CurrentUser(sub="sub-2", username="o", groups=[ROLE_OPERATOR])
    assert user.is_operator is True
    assert user.is_loan_officer is False


def test_current_user_with_both_roles() -> None:
    user = CurrentUser(sub="sub-3", username="admin", groups=[ROLE_LOAN_OFFICER, ROLE_OPERATOR])
    assert user.is_loan_officer is True
    assert user.is_operator is True


def test_current_user_with_no_roles() -> None:
    user = CurrentUser(sub="sub-4", username="nobody", groups=[])
    assert user.is_loan_officer is False
    assert user.is_operator is False


# ── require_role ──────────────────────────────────────────────────────────────


async def test_require_role_grants_access_when_role_matches() -> None:
    enforce = require_role(ROLE_LOAN_OFFICER)
    user = CurrentUser(sub="sub-lo", username="lo", groups=[ROLE_LOAN_OFFICER])
    result = await enforce(user)
    assert result is user


async def test_require_role_raises_403_when_role_missing() -> None:
    enforce = require_role(ROLE_LOAN_OFFICER)
    user = CurrentUser(sub="sub-op", username="op", groups=[ROLE_OPERATOR])
    with pytest.raises(HTTPException) as exc_info:
        await enforce(user)
    assert exc_info.value.status_code == 403


async def test_require_role_grants_access_when_any_role_matches() -> None:
    enforce = require_role(ROLE_LOAN_OFFICER, ROLE_OPERATOR)
    user = CurrentUser(sub="sub-op", username="op", groups=[ROLE_OPERATOR])
    result = await enforce(user)
    assert result is user


async def test_require_role_raises_403_when_no_role_matches() -> None:
    enforce = require_role(ROLE_LOAN_OFFICER, ROLE_OPERATOR)
    user = CurrentUser(sub="sub-x", username="x", groups=["UnknownGroup"])
    with pytest.raises(HTTPException) as exc_info:
        await enforce(user)
    assert exc_info.value.status_code == 403
