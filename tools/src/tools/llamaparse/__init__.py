"""LlamaParse tool — ``tools.llamaparse.parse_financial_pdf`` (P4-T1).

Public interface
----------------
``parse_financial_pdf(request)``
    Synchronous entry point called by the document-extraction subgraph
    (agents.subgraphs.document) and the AgentCore Gateway tool handler.

    Flow:
      1. Download PDF bytes from S3 using boto3.
      2. Upload bytes to LlamaParse via ``/api/v1/parsing/upload``.
      3. Poll ``/api/v1/parsing/job/{job_id}`` until SUCCESS or FAILURE.
      4. Fetch markdown result from ``/api/v1/parsing/job/{job_id}/result/markdown``.
      5. Normalize raw output → canonical schemas via ``tools.llamaparse.normalize``.

``_use_fixture_stub(request)``
    Offline fallback returning deterministic fixture data when
    ``LLAMA_CLOUD_API_KEY`` is absent (for CI / local dev without credentials).
"""

from tools.llamaparse.client import LlamaParseClient
from tools.llamaparse.models import LlamaParseRequest, LlamaParseResponse
from tools.llamaparse.normalize import normalize_response

__all__ = [
    "LlamaParseRequest",
    "LlamaParseResponse",
    "parse_financial_pdf",
]


def parse_financial_pdf(request: LlamaParseRequest) -> LlamaParseResponse:
    """Parse a financial PDF via LlamaParse and return a normalized response.

    Args:
        request: Validated :class:`LlamaParseRequest`.

    Returns:
        :class:`LlamaParseResponse` with structured fields, raw markdown, and
        confidence notes.  When ``LLAMA_CLOUD_API_KEY`` is unset, a
        deterministic fixture stub is returned for offline use.
    """
    client = LlamaParseClient()
    if not client.is_configured():
        from tools.llamaparse.stub import use_fixture_stub

        return use_fixture_stub(request)

    raw = client.parse(request)
    return normalize_response(raw, request)
