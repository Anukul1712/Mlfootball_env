from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


EXCLUDED_DIRECTORIES = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", "logs", "tmp"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def package(source: Path, output: Path) -> int:
    source = source.resolve()
    output = output.resolve()
    if not source.is_dir():
        raise ValueError(f"Submission folder does not exist: {source}")
    if output == source or source in output.parents:
        raise ValueError("Output ZIP must be outside the submission folder")
    output.parent.mkdir(parents=True, exist_ok=True)
    included = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            if any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
                continue
            if path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            archive.write(path, relative.as_posix())
            included += 1
    return included


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a clean participant submission ZIP")
    parser.add_argument("source", help="Submission folder whose contents become the ZIP root")
    parser.add_argument("output", help="Output .zip path")
    args = parser.parse_args()
    count = package(Path(args.source), Path(args.output))
    print(f"Created {Path(args.output).resolve()} with {count} files")


if __name__ == "__main__":
    main()
