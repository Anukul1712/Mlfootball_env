from __future__ import annotations

import argparse
import json
from pathlib import Path

from submission_checker import check_archive


BASE_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official static submission safety checks")
    parser.add_argument("archive")
    parser.add_argument("--report")
    args = parser.parse_args()
    report = check_archive(args.archive, BASE_DIRECTORY / "config" / "submission_policy.json")
    print("PASS" if report.passed else "FAIL")
    print(f"SHA-256: {report.sha256}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
