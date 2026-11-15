#!/usr/bin/env python3
"""Dump the backend's OpenAPI schema to a file for frontend type generation.

The running app disables /openapi.json; this builds the schema offline instead.
Usage (from backend/): uv run python ../scripts/export_openapi.py ../frontend/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from passcheck.config import Settings
from passcheck.main import create_app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    app = create_app(Settings(static_dir=Path("/nonexistent")), sources=[], start_scheduler=False)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
