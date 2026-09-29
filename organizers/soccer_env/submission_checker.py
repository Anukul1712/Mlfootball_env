from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


DEPENDENCY_NAME = re.compile(r"^([A-Za-z0-9_.-]+)")
SHELL_CHARACTERS = set(";&|><\r\n")


@dataclass
class CheckReport:
    archive: str
    sha256: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    model_files: list[str] = field(default_factory=list)
    team_name: str | None = None
    command: list[str] = field(default_factory=list)
    compressed_bytes: int = 0
    uncompressed_bytes: int = 0

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "archive": self.archive,
            "sha256": self.sha256,
            "team_name": self.team_name,
            "command": self.command,
            "compressed_bytes": self.compressed_bytes,
            "uncompressed_bytes": self.uncompressed_bytes,
            "file_count": len(self.files),
            "dependencies": self.dependencies,
            "model_files": self.model_files,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def load_policy(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _megabytes(value: int) -> float:
    return value / (1024 * 1024)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_path(name: str) -> str | None:
    if "\\" in name or "\x00" in name:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _read_text(archive: zipfile.ZipFile, name: str, maximum: int = 1_000_000) -> str:
    info = archive.getinfo(name)
    if info.file_size > maximum:
        raise ValueError(f"{name} is too large to inspect as text")
    return archive.read(info).decode("utf-8")


def _validate_command(report: CheckReport, names: set[str]) -> None:
    if not report.command:
        report.errors.append("submission.json must contain a non-empty command array")
        return
    if any(not isinstance(part, str) or not part for part in report.command):
        report.errors.append("Every launch-command item must be a non-empty string")
        return
    if any(any(character in part for character in SHELL_CHARACTERS) for part in report.command):
        report.errors.append("Launch command contains shell control characters")
    if report.command[0].lower() not in {"python", "python3"}:
        report.errors.append("The competition kit currently permits Python launch commands only")
        return
    if len(report.command) < 2:
        report.errors.append("Launch command does not name a Python module or script")
        return
    if report.command[1] == "-m":
        if len(report.command) < 3 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", report.command[2]):
            report.errors.append("The value after python -m must be a valid module name")
            return
        module_path = report.command[2].replace(".", "/")
        if f"{module_path}.py" not in names and f"{module_path}/__main__.py" not in names:
            report.errors.append(f"Launch module {report.command[2]!r} is not present in the archive")
    else:
        script = _normal_path(report.command[1])
        if script is None or script not in names:
            report.errors.append(f"Launch script {report.command[1]!r} is not present in the archive")

    for index, part in enumerate(report.command[:-1]):
        if part == "--model":
            model_path = _normal_path(report.command[index + 1])
            if model_path is None or model_path not in names:
                report.errors.append(f"Configured model file {report.command[index + 1]!r} is missing")


def check_archive(
    archive_path: str | Path,
    policy_path: str | Path | None = None,
) -> CheckReport:
    path = Path(archive_path)
    if policy_path is None:
        policy_path = Path(__file__).resolve().parents[1] / "config" / "submission_policy.json"
    policy = load_policy(policy_path)
    report = CheckReport(
        archive=str(path.resolve()),
        sha256=_sha256(path) if path.is_file() else "",
        compressed_bytes=path.stat().st_size if path.is_file() else 0,
    )
    if not path.is_file():
        report.errors.append("Archive does not exist")
        return report
    if path.suffix.lower() != ".zip":
        report.errors.append("Submission must be a .zip archive")
        return report
    if _megabytes(report.compressed_bytes) > policy["maximum_archive_mb"]:
        report.errors.append(f"Archive exceeds {policy['maximum_archive_mb']} MB")

    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        report.errors.append(f"Invalid ZIP archive: {error}")
        return report

    with archive:
        infos = archive.infolist()
        files = [info for info in infos if not info.is_dir()]
        if len(files) > policy["maximum_files"]:
            report.errors.append(f"Archive contains more than {policy['maximum_files']} files")

        seen_casefolded: set[str] = set()
        valid_names: set[str] = set()
        allowed_extensions = {item.lower() for item in policy["allowed_extensions"]}
        forbidden_extensions = {item.lower() for item in policy["forbidden_extensions"]}
        forbidden_directories = {item.casefold() for item in policy["forbidden_directories"]}
        forbidden_filenames = {item.casefold() for item in policy["forbidden_filenames"]}

        for info in files:
            name = _normal_path(info.filename)
            if name is None:
                report.errors.append(f"Unsafe archive path: {info.filename!r}")
                continue
            report.files.append(name)
            valid_names.add(name)
            folded = name.casefold()
            if folded in seen_casefolded:
                report.errors.append(f"Duplicate or case-colliding path: {name}")
            seen_casefolded.add(folded)

            pure = PurePosixPath(name)
            if any(part.casefold() in forbidden_directories for part in pure.parts[:-1]):
                report.errors.append(f"Forbidden generated or environment directory: {name}")
            if pure.name.casefold() in forbidden_filenames:
                report.errors.append(f"Forbidden secret-bearing filename: {name}")
            suffix = pure.suffix.lower()
            if suffix in forbidden_extensions:
                report.errors.append(f"Forbidden executable or secret file type: {name}")
            elif suffix not in allowed_extensions:
                report.errors.append(f"File type is not allowed by policy: {name}")
            unix_mode = info.external_attr >> 16
            if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                report.errors.append(f"Symbolic links are not allowed: {name}")
            if info.flag_bits & 0x1:
                report.errors.append(f"Encrypted ZIP members are not allowed: {name}")
            if _megabytes(info.file_size) > policy["maximum_single_file_mb"]:
                report.errors.append(f"File exceeds {policy['maximum_single_file_mb']} MB: {name}")
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > policy["maximum_compression_ratio"]:
                report.errors.append(f"Suspicious compression ratio ({ratio:.0f}:1): {name}")

        report.uncompressed_bytes = sum(info.file_size for info in files)
        if _megabytes(report.uncompressed_bytes) > policy["maximum_uncompressed_mb"]:
            report.errors.append(f"Expanded archive exceeds {policy['maximum_uncompressed_mb']} MB")

        for required in policy["required_files"]:
            if required not in valid_names:
                report.errors.append(f"Required file is missing from archive root: {required}")

        report.model_files = sorted(
            name for name in valid_names
            if PurePosixPath(name).suffix.lower() in {".bin", ".onnx", ".pt", ".pth", ".pkl", ".joblib", ".npz", ".npy"}
            or "/models/" in f"/{name}"
        )
        if not report.model_files:
            report.warnings.append("No model file was detected; this is acceptable only for code-only policies")

        if "submission.json" in valid_names:
            try:
                descriptor = json.loads(_read_text(archive, "submission.json"))
                report.team_name = descriptor.get("name")
                report.command = descriptor.get("command", [])
                if not isinstance(report.team_name, str) or not report.team_name.strip():
                    report.errors.append("submission.json must contain a non-empty team name")
                _validate_command(report, valid_names)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                report.errors.append(f"Cannot read submission.json: {error}")

        if "requirements.txt" in valid_names:
            try:
                requirements = _read_text(archive, "requirements.txt")
                allowed_dependencies = {name.casefold() for name in policy["allowed_dependencies"]}
                for line in requirements.splitlines():
                    requirement = line.strip()
                    if not requirement or requirement.startswith("#"):
                        continue
                    if any(token in requirement.lower() for token in ("http://", "https://", "git+", "file:", "-e ", "--")):
                        report.errors.append(f"Remote, local, or installer-option dependency is not allowed: {requirement}")
                        continue
                    match = DEPENDENCY_NAME.match(requirement)
                    if not match:
                        report.errors.append(f"Cannot parse dependency: {requirement}")
                        continue
                    name = match.group(1)
                    report.dependencies.append(requirement)
                    if name.casefold() not in allowed_dependencies:
                        report.errors.append(f"Dependency is not on the organizer allowlist: {name}")
            except (UnicodeDecodeError, ValueError) as error:
                report.errors.append(f"Cannot read requirements.txt: {error}")

    return report
