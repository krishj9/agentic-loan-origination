"""Export the FastAPI OpenAPI schema to backend/docs/openapi.json.

Run from the workspace root:
    uv run python backend/scripts/export_openapi.py

The committed snapshot allows Phase 5 (UI) to generate a typed client
from the OpenAPI contract before the backend is deployed.  A diff of
this file in CI catches accidental contract breaks (P2-T10 requirement).
"""

import json
import sys
from pathlib import Path

# Ensure backend/src is on the path when run without install
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "shared" / "src"))


def main() -> None:
    """Generate and write the OpenAPI JSON snapshot."""
    from backend.core.settings import Settings
    from backend.main import create_app

    # Boot the app with test-safe settings (no real AWS credentials needed)
    settings = Settings(
        app_env="development",
        log_level="WARNING",
        runtime_mode="local",
        cognito_user_pool_id="us-east-1_PLACEHOLDER",
        cognito_client_id="placeholder-client-id",
    )

    app = create_app(settings)
    schema = app.openapi()

    out_path = _REPO_ROOT / "backend" / "docs" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

    print(f"OpenAPI schema written to {out_path}")
    print(f"  title:   {schema.get('info', {}).get('title')}")
    print(f"  version: {schema.get('info', {}).get('version')}")
    print(f"  paths:   {len(schema.get('paths', {}))}")


if __name__ == "__main__":
    main()
