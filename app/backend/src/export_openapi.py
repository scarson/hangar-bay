"""Export the FastAPI OpenAPI schema to a JSON file for frontend codegen.

Usage: python src/export_openapi.py [output_path]
Default output: ../frontend/web/openapi.json (relative to app/backend/).

Importing fastapi_app.main requires environment configuration; this script
provides safe dummy defaults so codegen works in any environment. Real env
vars, when set, always take precedence (setdefault). The dummy values are
never used to open connections — only the schema is generated.
"""

import json
import os
import sys

_ENV_DEFAULTS = {
    "ESI_USER_AGENT": "hangar-bay-openapi-export (build tooling)",
    "AGGREGATION_REGION_IDS": "[10000002]",
    "DATABASE_URL": "postgresql+asyncpg://export:export@localhost:5432/export_dummy",
    "CACHE_URL": "redis://localhost:6379/15",
}
for _key, _value in _ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

from fastapi_app.main import app  # noqa: E402


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "../frontend/web/openapi.json"
    schema = app.openapi()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"OpenAPI schema written to {out_path} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
