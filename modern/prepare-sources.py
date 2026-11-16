#!/usr/bin/env python3
"""Restore pinned upstream sources and apply the reviewed modern P2 patches."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request

BUNDLE = pathlib.Path(__file__).resolve().parent
LOCK = json.loads((BUNDLE / "toolchain.lock.json").read_text())


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def checkout(name, dest):
    spec = LOCK[name]
    if not (dest / ".git").exists():
        dest.mkdir(parents=True, exist_ok=True)
        run("git", "init", str(dest))
        run("git", "remote", "add", "origin", spec["url"], cwd=dest)
        run("git", "fetch", "--depth=1", "origin", spec["revision"], cwd=dest)
        run("git", "checkout", "-b", "codex/p2-modern", "FETCH_HEAD", cwd=dest)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest, text=True).strip()
    if head != spec["revision"]:
        raise RuntimeError(f"{dest} has revision {head}; expected {spec['revision']}")


def patch(dest, name):
    patchfile = BUNDLE / "patches" / name
    args = ["git", "apply", "--check", str(patchfile)]
    if subprocess.run(args, cwd=dest, capture_output=True).returncode == 0:
        run("git", "apply", str(patchfile), cwd=dest)
    elif subprocess.run(["git", "apply", "--reverse", "--check", str(patchfile)],
                        cwd=dest, capture_output=True).returncode != 0:
        raise RuntimeError(f"{name} does not match {dest}; local changes preserved")


def main():
    work = pathlib.Path(sys.argv[1]).resolve()
    for name in ("llvm15-p2.patch", "tinygo-p2.patch", "p2llvm-tools.patch"):
        if not (BUNDLE / "patches" / name).is_file():
            raise RuntimeError(f"Missing reviewed patch: {name}")
    work.mkdir(parents=True, exist_ok=True)
    go = LOCK["go"]
    archive = work / f"go{go['version']}.tar.gz"
    if not archive.is_file():
        urllib.request.urlretrieve(go["linux_amd64_url"], archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != go["linux_amd64_sha256"]:
        raise RuntimeError("Go archive checksum mismatch")
    if not (work / "go/bin/go").is_file():
        with tarfile.open(archive) as source:
            source.extractall(work, filter="data")
    actual_go = subprocess.check_output([str(work / "go/bin/go"), "version"], text=True)
    if f"go{go['version']} " not in actual_go:
        raise RuntimeError(f"Unexpected Go installation: {actual_go.strip()}")
    checkout("p2llvm", work / "p2llvm")
    checkout("llvm", work / "p2llvm/llvm15")
    checkout("tinygo", work / "tinygo")
    patch(work / "p2llvm/llvm15", "llvm15-p2.patch")
    patch(work / "p2llvm", "p2llvm-tools.patch")
    patch(work / "tinygo", "tinygo-p2.patch")
    for source in sorted((BUNDLE / "overlays/tinygo").rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(BUNDLE / "overlays/tinygo")
        dest = work / "tinygo" / relative
        if dest.exists() and dest.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Local overlay changes preserved: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copyfile(source, dest)
    run("git", "submodule", "update", "--init", "--depth=1", "src/net", cwd=work / "tinygo")


if __name__ == "__main__":
    main()
