# Copyright and license notices

This repository is a source/evidence aggregation, not a relicensing of its contents. Copyright notices, license text, source headers and upstream provenance supplied by the sealed archives are preserved byte-for-byte.

- `src/tinygo/LICENSE`: TinyGo/Go authors, BSD-style terms and the upstream notice about LLVM portions.
- `src/go-llvm/LICENSE.txt`: Apache License 2.0 with LLVM Exceptions.
- `src/p2llvm/LICENSE`: original P2LLVM terms.
- `src/p2llvm/libc/LIB_LICENSE.txt`: multiple component licenses, including MIT/public domain/BSD and GPL with special exceptions; consult the file and individual source headers rather than assuming one license.
- `phase1/LICENSE`: original MIT handoff-file license. Its statement about upstream sources not being bundled describes that original Phase 1 handoff, not this Phase 2 source aggregation. It explicitly does not relicense downloaded upstream components.
- `binding/go-llvm-fc868cbb.bundle` preserves the controlled original source snapshot and its own license.

No new blanket repository license is imposed. Packaging-only additions are listed in `provenance/PACKAGING.md`; their presence does not change any third-party license. SDK/LLVM submodule trees not present in the sealed archive remain separately acquired, licensed inputs. No empty submodule directory is represented as a Git submodule or gitlink.

## Modern v0.1.0 release

The modern release separately redistributes Go 1.27.4, TinyGo 0.44.0, LLVM
15.0.7/Clang/LLD with the P2 backend, P2 compiler builtins, and loadp2. The SDK
keeps Go/TinyGo licenses in their source roots and additional component and Go
module notices under `licenses/`. The complete source archive preserves
licenses next to their upstream source files, including module dependencies.
The demo package includes TinyGo, Go, P2LLVM, P2 library, and loadp2 notices.

The source identities and all local port changes are recorded in
`modern/toolchain.lock.json`, `modern/source-manifest.json`,
`modern/release/loaders.lock.json`, and the three patches in `modern/patches/`.
The release's prepared-source manifest hashes the full resolved source inputs.
These packages do not relicense any upstream component. Newly authored modern
port runtime/machine files and tooling are offered under the BSD 3-Clause terms
in `modern/LICENSE`; existing headers and upstream terms take precedence for
derived files.
