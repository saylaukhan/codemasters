"""``make openapi`` entry point: ``python -m app.openapi_export <path/to/openapi.json>``.

Writes the OpenAPI schema of the application to the given file, creating parent directories.
The exported file is the single API contract (ADR-009) and is never edited by hand.
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def export_schema(target: Path) -> None:
    """Write the application's OpenAPI schema as pretty-printed JSON to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app().openapi()
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    """Parse the target path from ``argv`` and export the schema."""
    if len(argv) != 2:
        sys.stderr.write("использование: python -m app.openapi_export <путь к openapi.json>\n")
        return 2
    target = Path(argv[1])
    export_schema(target)
    sys.stdout.write(f"openapi: схема записана в {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
