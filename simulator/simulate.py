"""Agent simulator entry point.

T-01 stub: parses the arguments, prints the generation plan and exits with code 0.
The generator itself (device registration, measurement profiles, outages) lands in T-55.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_SCHOOLS = 350
DEFAULT_DEVICES = 1000
DEFAULT_DAYS = 90


def positive_int(value: str) -> int:
    """argparse type: a strictly positive integer."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(
            f"ожидается положительное целое число, получено {value}",
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simulate.py",
        description="Симулятор агентов: школы, ПК и история замеров для демо и нагрузки.",
    )
    parser.add_argument(
        "--schools",
        type=positive_int,
        default=DEFAULT_SCHOOLS,
        help=f"сколько школ (по умолчанию {DEFAULT_SCHOOLS})",
    )
    parser.add_argument(
        "--devices",
        type=positive_int,
        default=DEFAULT_DEVICES,
        help=f"сколько ПК (по умолчанию {DEFAULT_DEVICES})",
    )
    parser.add_argument(
        "--days",
        type=positive_int,
        default=DEFAULT_DAYS,
        help=f"глубина истории в днях (по умолчанию {DEFAULT_DAYS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lines = [
        "План симуляции:",
        f"  школ:       {args.schools}",
        f"  устройств:  {args.devices}",
        f"  дней:       {args.days}",
        "симулятор реализуется в T-55",
    ]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
