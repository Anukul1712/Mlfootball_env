from __future__ import annotations

import argparse
import json
from pathlib import Path

from soccer_env.submission_checker import check_archive

BASE_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Statically inspect a participant submission ZIP without extracting or running it")
    parser.add_argument("archive", help="Participant .zip file")
    parser.add_argument("--policy", default=str(BASE_DIRECTORY / "config" / "submission_policy.json"))
    parser.add_argument("--report", help="Optional JSON report output path")
    args = parser.parse_args()
    report = check_archive(args.archive, args.policy)

    print("PASS" if report.passed else "FAIL")
    print(f"Archive: {report.archive}")
    print(f"SHA-256: {report.sha256}")
    print(f"Team: {report.team_name or '-'}")
    print(f"Files: {len(report.files)} | compressed={report.compressed_bytes} | expanded={report.uncompressed_bytes}")
    print(f"Command: {json.dumps(report.command)}")
    print(f"Dependencies: {', '.join(report.dependencies) or 'none'}")
    print(f"Models: {', '.join(report.model_files) or 'none detected'}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")

    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"Report: {output.resolve()}")
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
