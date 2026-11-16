#!/usr/bin/env python3
"""Export reviewed source changes from the development tree into this bundle."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

BUNDLE = pathlib.Path(__file__).resolve().parent
GENERATED = {"lib/p2/libcompiler_builtins.a"}
SOURCE_ROOTS = {"src", "targets", "tools", "compiler", "builder", "compileopts"}
SOURCE_SUFFIXES = {".go", ".S", ".c", ".h", ".ld", ".json"}


def output(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=pathlib.Path)
    args = parser.parse_args()
    work = args.work.resolve()
    overlays = BUNDLE / "overlays/tinygo"
    sources = {}
    untracked = output(work / "tinygo", "ls-files", "--others", "--exclude-standard", "-z")
    for item in untracked.decode().split("\0"):
        if not item or item in GENERATED:
            continue
        relative = pathlib.Path(item)
        if relative.parts[0] not in SOURCE_ROOTS or relative.suffix not in SOURCE_SUFFIXES:
            raise RuntimeError(f"Review unexpected untracked source: {relative}")
        sources[relative] = work / "tinygo" / relative
    patches = BUNDLE / "patches"
    patches.mkdir(exist_ok=True)
    for repo, filename in ((work / "tinygo", "tinygo-p2.patch"),
                           (work / "p2llvm", "p2llvm-tools.patch"),
                           (work / "p2llvm/llvm15", "llvm15-p2.patch")):
        patch = output(repo, "diff", "--binary", "HEAD")
        if not patch:
            raise RuntimeError(f"Refusing empty source patch: {repo}")
        (patches / filename).write_bytes(patch)
    # An overlay promoted into a tracked patch must not survive as an old copy.
    # Only generated overlay files inside this exact bundle directory are pruned.
    for dest in overlays.rglob("*"):
        if dest.is_file() and dest.relative_to(overlays) not in sources:
            dest.resolve().relative_to(overlays.resolve())
            dest.unlink()
    for relative, source in sources.items():
        dest = overlays / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    files = {}
    for folder in (patches, overlays):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                files[path.relative_to(BUNDLE).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"schema": 1, "upstream": json.loads((BUNDLE / "toolchain.lock.json").read_text()), "sha256": files}
    (BUNDLE / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Exported three patches and {len(sources)} overlay files")


if __name__ == "__main__":
    main()