"""
Write the API's OpenAPI schema to web/openapi.json, without starting a server.

    python scripts/export_openapi.py

`npm run gen:api` in web/ runs this, then turns the schema into
web/src/lib/api-types.ts. CI runs both and fails if either file changes.

The schema must not depend on the machine it's made on, so the app is
imported from a temporary directory (no .env is read) with only the one
setting it needs.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "web" / "openapi.json"


def main() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    for name in [key for key in os.environ if key.startswith("OTB_")]:
        del os.environ[name]
    os.environ["OTB_SECRET_KEY"] = "openapi-export-only"
    os.environ["OTB_DATABASE_URL"] = "sqlite://"
    os.chdir(tempfile.gettempdir())

    from app.main import app

    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
