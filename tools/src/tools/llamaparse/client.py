"""LlamaParse API client — synchronous implementation with retry/polling (P4-T1).

Responsibilities
----------------
* Download PDF bytes from S3 (``incoming/{application_id}/``).
* Upload bytes to LlamaParse ``/api/v1/parsing/upload`` with document-type-specific
  parsing instructions (financial-document tuning per design §6.1).
* Poll ``/api/v1/parsing/job/{job_id}`` until SUCCESS / ERROR, bounded by
  ``MAX_POLL_ATTEMPTS`` and ``POLL_INTERVAL_SECONDS``.
* Fetch raw markdown from ``/api/v1/parsing/job/{job_id}/result/markdown``.
* Return a :class:`LlamaParseRawOutput` for the normalization layer.

Configuration
-------------
``LLAMA_CLOUD_API_KEY``   LlamaParse API key (required for live calls).
``AWS_REGION``            AWS region for boto3 S3 client (default: us-east-1).
``S3_BUCKET_NAME``        S3 bucket holding application documents.
"""

import os
import time
from typing import Any

import boto3
import httpx

from tools.llamaparse.models import LlamaParseRawOutput, LlamaParseRequest
from tools.log import get_logger

log = get_logger("llamaparse.client")

_BASE_URL = "https://api.cloud.llamaindex.ai"
_UPLOAD_PATH = "/api/v1/parsing/upload"
_JOB_STATUS_PATH = "/api/v1/parsing/job/{job_id}"
_JOB_RESULT_MARKDOWN_PATH = "/api/v1/parsing/job/{job_id}/result/markdown"

MAX_POLL_ATTEMPTS = 20
POLL_INTERVAL_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 30.0

# Financial-document tuned instructions per document type (design §6.1)
_PARSE_INSTRUCTIONS: dict[str, str] = {
    "PAYSTUB": (
        "This is a pay stub financial document. "
        "Extract the following fields as structured key-value pairs: "
        "employee_name, employer_name, pay_period_start (YYYY-MM-DD), "
        "pay_period_end (YYYY-MM-DD), pay_date (YYYY-MM-DD), "
        "gross_pay (decimal USD), deductions (decimal USD), net_pay (decimal USD), "
        "ytd_gross_pay (decimal USD, if present), ytd_net_pay (decimal USD, if present). "
        "Preserve all monetary values as decimal strings with two decimal places."
    ),
    "BANK_STATEMENT": (
        "This is a bank statement financial document. "
        "Extract the following fields as structured key-value pairs: "
        "account_holder_name, statement_period_start (YYYY-MM-DD), "
        "statement_period_end (YYYY-MM-DD), account_number_masked (e.g. ****1234), "
        "opening_balance (decimal USD), closing_balance (decimal USD). "
        "Also extract all transaction rows as a table with columns: "
        "date (YYYY-MM-DD), description, amount (decimal USD, negative=debit), balance (decimal USD). "
        "Preserve all monetary values as decimal strings with two decimal places."
    ),
    "auto": (
        "This is a financial document. Extract all structured fields and tables "
        "as key-value pairs and tabular rows."
    ),
}


class LlamaParseClient:
    """Synchronous LlamaParse client with S3 download, upload, and polling."""

    def __init__(self) -> None:
        self._api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
        self._bucket = os.environ.get("S3_BUCKET_NAME", "loan-origination-documents-demo")
        self._region = os.environ.get("AWS_REGION", "us-east-1")

    def is_configured(self) -> bool:
        """Return True if a LlamaParse API key is present in the environment."""
        return bool(self._api_key)

    def _correlation(self, request: LlamaParseRequest) -> dict[str, str | None]:
        return {
            "application_id": request.application_id,
            "document_id": request.document_id,
        }

    def _download_from_s3(self, s3_key: str, application_id: str) -> bytes:
        """Download the PDF bytes from S3.

        Args:
            s3_key: Full S3 object key (e.g. ``incoming/{application_id}/doc.pdf``).
            application_id: For structured log correlation.

        Returns:
            Raw PDF bytes.

        Raises:
            RuntimeError: If the S3 download fails.
        """
        s3 = boto3.client("s3", region_name=self._region)
        log.debug(
            "downloading document from S3",
            correlation={"application_id": application_id},
            s3_key=s3_key,
            bucket=self._bucket,
        )
        response = s3.get_object(Bucket=self._bucket, Key=s3_key)
        body: bytes = response["Body"].read()
        log.debug(
            "S3 download complete",
            correlation={"application_id": application_id},
            bytes_downloaded=len(body),
        )
        return body

    def _upload_to_llamaparse(
        self,
        pdf_bytes: bytes,
        filename: str,
        parse_instructions: str,
        correlation: dict[str, str | None],
    ) -> str:
        """Upload PDF bytes to LlamaParse and return the job_id.

        Args:
            pdf_bytes: Raw PDF content.
            filename: Filename used in the multipart upload.
            parse_instructions: Financial-tuned extraction instructions.
            correlation: Log correlation fields.

        Returns:
            LlamaParse job ID string.

        Raises:
            httpx.HTTPStatusError: If the upload request fails.
        """
        log.info("uploading document to LlamaParse", correlation=correlation)
        with httpx.Client(base_url=_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.post(
                _UPLOAD_PATH,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (filename, pdf_bytes, "application/pdf")},
                data={"parsing_instruction": parse_instructions},
            )
            resp.raise_for_status()
            job_id: str = resp.json()["id"]
        log.info("LlamaParse upload accepted", correlation=correlation, job_id=job_id)
        return job_id

    def _poll_job(self, job_id: str, correlation: dict[str, str | None]) -> None:
        """Poll until the LlamaParse job reaches SUCCESS or fails.

        Args:
            job_id: LlamaParse job identifier.
            correlation: Log correlation fields.

        Raises:
            RuntimeError: If the job fails or polling is exhausted.
        """
        status_url = _JOB_STATUS_PATH.format(job_id=job_id)
        with httpx.Client(base_url=_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
            for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
                resp = client.get(
                    status_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                status: str = data.get("status", "UNKNOWN")
                log.debug(
                    "LlamaParse job poll",
                    correlation=correlation,
                    job_id=job_id,
                    attempt=attempt,
                    status=status,
                )
                if status == "SUCCESS":
                    return
                if status in {"ERROR", "CANCELLED"}:
                    raise RuntimeError(
                        f"LlamaParse job {job_id} reached terminal status: {status}"
                    )
                time.sleep(POLL_INTERVAL_SECONDS)
        raise RuntimeError(
            f"LlamaParse job {job_id} did not complete after {MAX_POLL_ATTEMPTS} attempts"
        )

    def _fetch_markdown(self, job_id: str, correlation: dict[str, str | None]) -> str:
        """Fetch the markdown result from a completed LlamaParse job.

        Args:
            job_id: Completed LlamaParse job identifier.
            correlation: Log correlation fields.

        Returns:
            Raw markdown string of the parsed document.

        Raises:
            httpx.HTTPStatusError: If the result request fails.
        """
        result_url = _JOB_RESULT_MARKDOWN_PATH.format(job_id=job_id)
        with httpx.Client(base_url=_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(
                result_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            body = resp.json()

        # LlamaParse returns {"markdown": "...", "pages": [...]}
        markdown: str = body.get("markdown", "")
        pages: list[dict[str, Any]] = body.get("pages", [])
        log.info(
            "LlamaParse result fetched",
            correlation=correlation,
            job_id=job_id,
            page_count=len(pages),
            markdown_length=len(markdown),
        )
        return markdown

    def parse(self, request: LlamaParseRequest) -> LlamaParseRawOutput:
        """End-to-end parse: S3 download → upload → poll → result.

        Args:
            request: Validated :class:`LlamaParseRequest`.

        Returns:
            :class:`LlamaParseRawOutput` with job_id, raw markdown, and metadata.

        Raises:
            RuntimeError: If S3 download or LlamaParse job fails.
            httpx.HTTPStatusError: On non-2xx HTTP responses.
        """
        ctx = self._correlation(request)
        log.info("starting LlamaParse parse", correlation=ctx, document_type=str(request.document_type))

        # 1. Download from S3
        pdf_bytes = self._download_from_s3(request.s3_key, request.application_id)

        # 2. Select parse instructions
        instructions = _PARSE_INSTRUCTIONS.get(
            str(request.document_type),
            _PARSE_INSTRUCTIONS["auto"],
        )

        # 3. Upload to LlamaParse
        filename = request.s3_key.rsplit("/", 1)[-1] or f"{request.document_id}.pdf"
        job_id = self._upload_to_llamaparse(pdf_bytes, filename, instructions, ctx)

        # 4. Poll to completion
        self._poll_job(job_id, ctx)

        # 5. Fetch markdown
        markdown = self._fetch_markdown(job_id, ctx)

        log.info("LlamaParse parse complete", correlation=ctx, job_id=job_id)
        return LlamaParseRawOutput(
            job_id=job_id,
            raw_markdown=markdown,
            metadata={
                "source": "llamaparse_api",
                "document_type": str(request.document_type),
                "s3_key": request.s3_key,
            },
        )
