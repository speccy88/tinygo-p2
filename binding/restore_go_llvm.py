#!/usr/bin/env python3
"""Cold-restore the controlled go-llvm snapshot without a module-cache write.

The local Git bundle is a controlled snapshot; the separately pinned upstream
module ZIP supplies the immutable pre-patch source identity.  This tool binds
one compatibility patch to the phase-2 patch manifest before cloning anything.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SNAPSHOT = "fc868cbb5731eda2886115d93f83655a31fc4745"
UPSTREAM = "v0.0.0-20220420140351-512c94c1e71f"
MODULE = "tinygo.org/x/go-llvm"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fail(message):
    raise SystemExit(message)


def run(args, cwd=None):
    process = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    if process.returncode:
        raise RuntimeError("command failed: " + " ".join(args) + "\n" + process.stderr)
    return process.stdout.strip()


def zip_files(path):
    with zipfile.ZipFile(path) as archive:
        return [{"path": item.filename,
                 "sha256": hashlib.sha256(archive.read(item)).hexdigest(),
                 "bytes": item.file_size}
                for item in sorted(archive.infolist(), key=lambda item: item.filename)
                if not item.is_dir()]


def binding_record(path):
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != 2:
        fail("unsupported patch binding manifest schema")
    records = [entry for entry in manifest.get("patches", [])
               if entry.get("name") == "go-llvm"]
    if len(records) != 1:
        fail("binding manifest must contain exactly one go-llvm patch record")
    record = records[0]
    if record.get("before_head") != SNAPSHOT:
        fail("binding manifest controlled snapshot mismatch")
    if not isinstance(record.get("patch_sha256"), str):
        fail("binding manifest lacks compatibility patch digest")
    files = record.get("files")
    if not isinstance(files, list) or not files:
        fail("binding manifest lacks intended-file identities")
    for item in files:
        if not all(isinstance(item.get(key), str) for key in ("path", "before_sha256", "after_sha256")):
            fail("binding manifest has incomplete intended-file identity")
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--upstream-zip", required=True)
    parser.add_argument("--upstream-manifest", required=True)
    parser.add_argument("--binding-manifest", required=True)
    parser.add_argument("--compat-patch", required=True)
    parser.add_argument("--destination", required=True)
    ns = parser.parse_args()
    bundle, upstream, upstream_manifest, binding_manifest, patch, dst = [
        Path(value).resolve() for value in
        (ns.bundle, ns.upstream_zip, ns.upstream_manifest, ns.binding_manifest,
         ns.compat_patch, ns.destination)]

    record = binding_record(binding_manifest)
    # Validate all supplied immutable inputs before creating the destination.
    if sha(patch) != record["patch_sha256"]:
        fail("compatibility patch digest does not match binding manifest")
    module_manifest = json.loads(upstream_manifest.read_text())
    if module_manifest.get("module") != MODULE or module_manifest.get("upstream_module_revision") != UPSTREAM:
        fail("wrong upstream module identity")
    module_files = module_manifest.get("files")
    if sha(upstream) != module_manifest.get("zip_sha256") or zip_files(upstream) != module_files:
        fail("pinned module ZIP full-tree comparison failed")
    root = f"{MODULE}@{UPSTREAM}/"
    upstream_by_relative = {}
    for item in module_files:
        path = item.get("path", "")
        if path.startswith(root):
            upstream_by_relative[path[len(root):]] = item
    for item in record["files"]:
        upstream_item = upstream_by_relative.get(item["path"])
        if not upstream_item or upstream_item.get("sha256") != item["before_sha256"]:
            fail("binding manifest pre-patch file does not match pinned upstream ZIP: " + item["path"])
    if dst.exists():
        fail("destination must be absent: " + str(dst))

    # Clone rejects an invalid bundle. Verify the checked-out snapshot and every
    # intended pre-patch file before permitting git apply.
    try:
        run(["git", "clone", str(bundle), str(dst)])
        run(["git", "bundle", "verify", str(bundle)], dst)
        if run(["git", "rev-parse", "HEAD"], dst) != SNAPSHOT:
            fail("controlled snapshot HEAD mismatch")
        if run(["git", "status", "--porcelain"], dst):
            fail("controlled snapshot is unexpectedly dirty")
        for item in record["files"]:
            restored = dst / item["path"]
            if not restored.is_file() or sha(restored) != item["before_sha256"]:
                fail("restored snapshot pre-patch identity mismatch: " + item["path"])
        run(["git", "apply", "--check", str(patch)], dst)
        run(["git", "apply", str(patch)], dst)
        for item in record["files"]:
            restored = dst / item["path"]
            if not restored.is_file() or sha(restored) != item["after_sha256"]:
                fail("restored snapshot post-patch identity mismatch: " + item["path"])
        second = subprocess.run(["git", "apply", "--check", str(patch)], cwd=dst,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if second.returncode == 0:
            fail("compatibility patch unexpectedly applies twice")
        run(["git", "apply", "--reverse", "--check", str(patch)], dst)
    except Exception:
        shutil.rmtree(dst, ignore_errors=True)
        raise
    print(json.dumps({"status": "PASS", "controlled_snapshot_head": SNAPSHOT,
                      "upstream_module_revision": UPSTREAM,
                      "upstream_zip_sha256": module_manifest["zip_sha256"],
                      "compatibility_patch_sha256": record["patch_sha256"],
                      "intended_files": record["files"],
                      "destination": str(dst)}, sort_keys=True))


if __name__ == "__main__":
    main()
