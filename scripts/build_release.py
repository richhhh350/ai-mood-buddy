"""Build a source-only ZIP from an explicit allowlist. Never include .env or data."""
import argparse
import hashlib
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = {"README.md", "requirements.txt", "requirements.lock", ".env.example", ".gitignore", "start.cmd"}
SOURCE_DIRS = {"app", "tests", "docs", "scripts"}
SUFFIXES = {".py", ".cjs", ".js", ".html", ".css", ".md"}


def build(output):
    paths = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in {".venv", "__pycache__", ".git", "data"} for part in relative.parts):
            continue
        allowed = relative.as_posix() in TOP_FILES or (
            relative.parts[0] in SOURCE_DIRS and path.suffix in SUFFIXES)
        if not allowed or not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("Refusing symlink in release")
        # A guardrail, not an exhaustive secret scanner. Print only the filename on failure.
        if re.search(rb"sk-[A-Za-z0-9_-]{20,}", path.read_bytes()):
            raise ValueError(f"Possible secret in {relative}; release aborted")
        paths.append(path)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, f"ai-mood-buddy/{path.relative_to(ROOT).as_posix()}")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return len(paths), digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count, digest = build(args.output)
    print(f"Release files: {count}; SHA256: {digest}")
