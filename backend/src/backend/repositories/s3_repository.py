"""Async S3 repository using aioboto3.

All AWS interactions run inside an async context manager so they never
block the uvicorn event loop.  boto3 calls that lack native async support
(e.g. generate_presigned_url) are dispatched via asyncio.get_event_loop()
.run_in_executor() to keep them off the event loop thread.

Org comms rule: all outbound calls have timeouts (set on the aioboto3
client config) and use TLS (boto3/aioboto3 default).
"""

import asyncio
import json
import logging
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from backend.core.settings import Settings

log = logging.getLogger(__name__)

_BOTO_CONFIG = Config(
    connect_timeout=5,
    read_timeout=30,
    retries={"max_attempts": 3, "mode": "adaptive"},
)


class S3Repository:
    """Thin async wrapper around aioboto3 S3 operations.

    One instance per request via FastAPI DI — the aioboto3 Session is
    lightweight and does not pool connections at construction time.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region,
        )

    def _client_kwargs(self) -> dict[str, Any]:
        """Build the kwargs dict for the S3 client constructor."""
        kwargs: dict[str, Any] = {
            "region_name": self._settings.aws_region,
            "config": _BOTO_CONFIG,
        }
        if self._settings.s3_endpoint_url:
            kwargs["endpoint_url"] = self._settings.s3_endpoint_url
        return kwargs

    async def put_json(self, key: str, data: dict[str, Any]) -> None:
        """Serialise `data` to JSON and write it to S3 at `key`.

        Args:
            key:  Full S3 object key (no bucket prefix).
            data: JSON-serialisable dictionary.
        """
        body = json.dumps(data, default=str).encode()
        async with self._session.client("s3", **self._client_kwargs()) as s3:
            await s3.put_object(
                Bucket=self._settings.s3_bucket_name,
                Key=key,
                Body=body,
                ContentType="application/json",
            )
        log.debug(
            "S3 put_json completed",
            extra={"bucket": self._settings.s3_bucket_name, "key": key, "bytes": len(body)},
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Fetch and deserialise a JSON object from S3.

        Returns:
            Parsed dictionary, or None when the key does not exist.
        """
        async with self._session.client("s3", **self._client_kwargs()) as s3:
            try:
                response = await s3.get_object(
                    Bucket=self._settings.s3_bucket_name,
                    Key=key,
                )
                body = await response["Body"].read()
                return json.loads(body)  # type: ignore[no-any-return]
            except ClientError as exc:
                error_code = exc.response["Error"]["Code"]
                if error_code in ("NoSuchKey", "404"):
                    log.debug(
                        "S3 key not found",
                        extra={"bucket": self._settings.s3_bucket_name, "key": key},
                    )
                    return None
                raise

    async def generate_presigned_put(
        self,
        key: str,
        content_type: str = "application/pdf",
        expires_in: int = 900,
    ) -> str:
        """Generate a presigned PUT URL for direct client-to-S3 upload.

        boto3's generate_presigned_url is synchronous, so we dispatch it
        to a thread executor to avoid blocking the event loop.

        Args:
            key:          S3 object key the client will write to.
            content_type: Content-Type header the client must send.
            expires_in:   URL validity in seconds.

        Returns:
            Presigned HTTPS PUT URL.
        """
        loop = asyncio.get_event_loop()
        url: str = await loop.run_in_executor(
            None,
            self._generate_presigned_put_sync,
            key,
            content_type,
            expires_in,
        )
        log.debug(
            "Presigned PUT URL generated",
            extra={
                "bucket": self._settings.s3_bucket_name,
                "key": key,
                "expires_in": expires_in,
            },
        )
        return url

    def _generate_presigned_put_sync(
        self,
        key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        """Synchronous presigned-URL generation (runs in thread executor)."""
        import boto3  # standard boto3 for sync presign

        session = boto3.Session(
            profile_name=self._settings.aws_profile,
            region_name=self._settings.aws_region,
        )
        kwargs: dict[str, Any] = {}
        if self._settings.s3_endpoint_url:
            kwargs["endpoint_url"] = self._settings.s3_endpoint_url

        s3 = session.client("s3", **kwargs)
        return s3.generate_presigned_url(  # type: ignore[no-any-return]
            "put_object",
            Params={
                "Bucket": self._settings.s3_bucket_name,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    async def key_exists(self, key: str) -> bool:
        """Return True if the S3 object key exists in the bucket."""
        async with self._session.client("s3", **self._client_kwargs()) as s3:
            try:
                await s3.head_object(Bucket=self._settings.s3_bucket_name, Key=key)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
                raise
