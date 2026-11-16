#!/usr/bin/env python3
"""Stage release SDK/source trees from reviewed checkouts; create release archives.

Run on Linux. Only Git-listed source files and explicit build products are copied.
No .git directories, developer caches, serial logs, or credentials are included.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

BUNDLE = Path(__file__).resolve().parents[1]
REPO = BUNDLE.parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest, follow_symlinks=False)


def copy_sources(source, dest, extra=False, prefix=None):
    args = ["git", "ls-files", "-z", "--cached"]
    if extra:
        args += ["--others", "--exclude-standard"]
    if prefix:
        args += ["--", prefix]
    names = subprocess.check_output(args, cwd=source).decode().split("\0")
    for name in sorted(set(names)):
        path = source / name
        if name and (path.is_file() or path.is_symlink()):
            copy(path, dest / name)


def bundle(dest):
    copy_sources(REPO, dest, extra=True, prefix="modern")
    copy(REPO / "README.md", dest / "README.md")
    copy(REPO / "NOTICE.md", dest / "NOTICE.md")


def stage(args):
    work, out = args.work, args.output
    sdk, sources = out / "tinygo-p2-sdk", out / "tinygo-p2-sources"
    if sdk.exists() or sources.exists():
        raise RuntimeError("Use an empty staging directory; existing files are preserved")
    for dest in (sdk, sources):
        dest.mkdir(parents=True)
        bundle(dest)
        copy_sources(work / "tinygo", dest / "tinygo")
        for path in (BUNDLE / "overlays/tinygo").rglob("*"):
            if path.is_file():
                copy(path, dest / "tinygo" / path.relative_to(BUNDLE / "overlays/tinygo"))
        copy_sources(work / "tinygo/src/net", dest / "tinygo/src/net")
    print("Staging patched LLVM and P2 support sources", flush=True)
    copy_sources(work / "p2llvm", sources / "p2llvm")
    copy_sources(work / "p2llvm/llvm15", sources / "p2llvm/llvm15")
    copy_sources(args.loadp2, sources / "loadp2")
    copy_sources(args.spin2cpp, sources / "spin2cpp")
    go_version = json.loads((BUNDLE / "toolchain.lock.json").read_text())["go"]["version"]
    copy(work / f"go{go_version}.tar.gz", sources / f"go{go_version}.tar.gz")
    shutil.copytree(work / "go", sdk / "go", symlinks=True)
    print("Downloading the exact Go module build inputs", flush=True)
    env = dict(os.environ, GOMODCACHE=str(sources / "gomodcache"))
    run(str(work / "go/bin/go"), "mod", "download", "all", cwd=sources / "tinygo", env=env)
    manifest = {"schema": 1, "toolchain": json.loads((BUNDLE / "toolchain.lock.json").read_text()),
                "patch_bundle_sha256": digest(BUNDLE / "source-manifest.json"), "files": {}}
    for root in ("tinygo", "p2llvm", "loadp2", "spin2cpp", "gomodcache"):
        for path in sorted((sources / root).rglob("*")):
            if path.is_file():
                manifest["files"][path.relative_to(sources).as_posix()] = digest(path)
    (sources / "prepared-source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Pinned {len(manifest['files'])} source/dependency files", flush=True)
    llvm = work / "llvm15-build"
    names = "clang clang++ clang-15 lld ld.lld llc opt llvm-config llvm-ar llvm-ranlib llvm-objcopy llvm-objdump llvm-readelf llvm-readobj llvm-nm llvm-as llvm-dis llvm-mc llvm-symbolizer llvm-addr2line FileCheck not count split-file"
    for name in names.split():
        copy(llvm / "bin" / name, sdk / "llvm15-build/bin" / name)
    for pattern in ("libLLVM*.so*", "libclang.so*"):
        for path in (llvm / "lib").glob(pattern):
            copy(path, sdk / "llvm15-build/lib" / path.name)
    shutil.copytree(llvm / "lib/clang", sdk / "llvm15-build/lib/clang", symlinks=True)
    resource = Path(subprocess.check_output([str(llvm / "bin/clang"), "-print-resource-dir"], text=True).strip())
    shutil.copytree(resource, sdk / "tinygo/lib/clang", symlinks=True)
    copy(work / "tinygo/lib/p2/libcompiler_builtins.a", sdk / "tinygo/lib/p2/libcompiler_builtins.a")
    print("Building relocatable TinyGo executable", flush=True)
    includes = [llvm / "include", work / "p2llvm/llvm15/llvm/include", work / "p2llvm/llvm15/clang/include", llvm / "tools/clang/include"]
    env = dict(os.environ, PATH=f"{work}/go/bin:{llvm}/bin:/usr/local/bin:/usr/bin:/bin",
               CGO_CPPFLAGS=" ".join(f'"-I{p}"' for p in includes),
               CGO_LDFLAGS=f'"-L{llvm}/lib"', LD_LIBRARY_PATH=str(llvm / "lib"),
               GOMODCACHE=str(sources / "gomodcache"), GOPROXY="off", GOSUMDB="off")
    run(str(work / "go/bin/go"), "build", "-p", "3", "-trimpath", "-tags", "llvm15", "-o", "build/tinygo", ".", cwd=sdk / "tinygo", env=env)
    run("patchelf", "--set-rpath", "$ORIGIN/../../llvm15-build/lib", str(sdk / "tinygo/build/tinygo"))
    for binary in (sdk / "llvm15-build/bin").iterdir():
        if not binary.is_symlink():
            run("patchelf", "--set-rpath", "$ORIGIN/../lib", str(binary))
    launcher = sdk / "bin/tinygo-p2"
    launcher.parent.mkdir()
    launcher.write_text('#!/usr/bin/env bash\nset -euo pipefail\nroot=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\nexport TINYGO_P2_WORK="$root"\nexec bash "$root/modern/tinygo.sh" "$@"\n')
    launcher.chmod(0o755)
    for name, source in (("LLVM", work / "p2llvm/llvm15/llvm/LICENSE.TXT"),
                         ("Clang", work / "p2llvm/llvm15/clang/LICENSE.TXT"),
                         ("LLD", work / "p2llvm/llvm15/lld/LICENSE.TXT"),
                         ("P2LLVM", work / "p2llvm/LICENSE"),
                         ("P2-libc", work / "p2llvm/libc/LIB_LICENSE.txt"),
                         ("loadp2", args.loadp2 / "LICENSE")):
        copy(source, sdk / "licenses" / f"{name}.txt")
    for dest in (sdk, sources):
        copy(BUNDLE / "release/SOURCE-BUILD.md", dest / "SOURCE-BUILD.md")
    print("SDK and complete source trees staged", flush=True)


def archives(args):
    out = args.output
    # Refresh documentation and release scripts after validation, before sealing.
    for name in ("tinygo-p2-sdk", "tinygo-p2-sources"):
        bundle(out / name)
        copy(BUNDLE / "release/SOURCE-BUILD.md", out / name / "SOURCE-BUILD.md")
        suffix = "ubuntu26.04-x86_64" if name.endswith("sdk") else "full"
        target = out / f"{name}-{args.version}-{suffix}.tar.gz"
        print(f"Compressing {target.name}", flush=True)
        def include(info):
            relative = Path(info.name).relative_to(name)
            # Compiler caches contain paths specific to the validation machine.
            # The source archive already contains the verified Go SDK tarball.
            if relative.parts and (relative.parts[0] == "cache" or
                    (name.endswith("sources") and relative.parts[0] == "go")):
                return None
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            return info
        with tarfile.open(target, "w:gz", compresslevel=6) as archive:
            archive.add(out / name, arcname=name, filter=include)
    demo = out / "tinygo-p2-demo"
    if not demo.exists():
        raise RuntimeError("Stage and validate the demo directory before sealing")
    target = out / f"tinygo-p2-demo-{args.version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(demo.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(out))
    assets = sorted(out.glob("*.tar.gz")) + sorted(out.glob("*.zip"))
    (out / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.name}\n" for p in assets))
    print((out / "SHA256SUMS").read_text(), flush=True)


def demo(args):
    out, work = args.output, args.work
    sdk, dest = out / "tinygo-p2-sdk", out / "tinygo-p2-demo"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("hello", "blink", "channels", "psram-store"):
        source = BUNDLE / "examples" / name / "main.go"
        copy(source, dest / "examples" / name / "main.go")
        run(str(sdk / "bin/tinygo-p2"), "build", "-target=p2", "-o",
            str(dest / f"{name}.elf"), str(source), cwd=BUNDLE / "examples")
        run("python3", str(BUNDLE / "export-image.py"), str(dest / f"{name}.elf"),
            str(dest / f"{name}.binary"))
    copy(BUNDLE / "examples/go.mod", dest / "examples/go.mod")
    copy(dest / "hello.binary", dest / "_BOOT_P2.BIX")
    copy(args.loadp2 / "build-win32/loadp2.exe", dest / "tools/loadp2.exe")
    copy(args.loadp2 / "build/loadp2", dest / "tools/loadp2-linux")
    copy(BUNDLE / "export-image.py", dest / "tools/export-image.py")
    copy(BUNDLE / "hil/p2ram.py", dest / "tools/hil/p2ram.py")
    copy(BUNDLE / "release/DEMO.md", dest / "README.md")
    copy(BUNDLE / "LICENSE", dest / "licenses/tinygo-p2.txt")
    for name, source in (("TinyGo", work / "tinygo/LICENSE"),
                         ("Go", work / "go/LICENSE"),
                         ("P2LLVM", work / "p2llvm/LICENSE"),
                         ("P2-libc", work / "p2llvm/libc/LIB_LICENSE.txt"),
                         ("loadp2", args.loadp2 / "LICENSE")):
        copy(source, dest / "licenses" / f"{name}.txt")
    # Preserve notices for Go dependencies compiled into the SDK executable.
    modules = out / "tinygo-p2-sources/gomodcache"
    for source in modules.rglob("*"):
        if source.is_file() and source.name.upper().startswith(("LICENSE", "NOTICE", "COPYING")):
            copy(source, sdk / "licenses/go-modules" / source.relative_to(modules))
    images = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
              for p in sorted(dest.iterdir()) if p.suffix in (".elf", ".binary", ".BIX")}
    (dest / "images.json").write_text(json.dumps(images, indent=2) + "\n")
    print("Demo images and component licenses staged", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "demo", "archives"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--loadp2", type=Path, required=True)
    parser.add_argument("--spin2cpp", type=Path, required=True)
    parser.add_argument("--version", default="v0.1.0")
    args = parser.parse_args()
    {"stage": stage, "demo": demo, "archives": archives}[args.phase](args)


if __name__ == "__main__":
    main()
