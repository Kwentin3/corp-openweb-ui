#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path


KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.match(key):
            raise ValueError(f"{path}:{line_number}: invalid env key {key!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("env_file")
    args = parser.parse_args()
    for key, value in parse_env_file(Path(args.env_file)).items():
        print(f"export {key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
