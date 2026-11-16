#!/usr/bin/env python3
"""Compile the complete Go code blocks copied verbatim from the main README."""
import argparse
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("sdk", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
blocks = re.findall(r"```go\n(.*?)\n```", (repo / "README.md").read_text(), re.S)
if len(blocks) != 5:
    raise RuntimeError(f"Expected five runnable tutorial programs, found {len(blocks)}")
for name, code in zip(("hello", "blink", "channels", "psram", "echo"), blocks):
    folder = args.output / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "main.go").write_text(code + "\n")
    (folder / "go.mod").write_text(f"module example.com/tutorial-{name}\n\ngo 1.27\n")
    subprocess.run([str(args.sdk / "bin/tinygo-p2"), "build", "-target=p2",
                    "-o", str(folder / "app.elf"), "."], cwd=folder, check=True)
    print(f"PASS README {name}", flush=True)
