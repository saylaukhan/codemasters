"""``make seed`` entry point: ``python -m app.seed``.

Reference data, VKO district GeoJSON and test schools arrive in T-04; dev users in T-20.
"""

import sys


def main() -> int:
    """Report that seeding is not implemented yet."""
    sys.stdout.write("seed: справочники и тестовые школы появятся в T-04\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
