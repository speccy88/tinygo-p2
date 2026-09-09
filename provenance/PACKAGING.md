# Packaging-only changes

The archived project/application/runtime source, upstream license texts and source headers are not rewritten for publication. `source-inventory.json` records the exact SHA-256 identity and archive member of each of the 2,223 imported files; `exclusions.json` records what stays out of Git and why. `archive-MANIFEST.sha256` retains the full Phase 2 archive manifest, not a claim that every member is in this reduced tree.

The following repository additions describe or verify the publication, rather than changing the experimental port:

- `README.md`: current scope, pinned external SDK, offline verification entry point and private publication links. Historical hardware evidence is distinguished from fresh host-only rebuilds.
- `.gitignore`: excludes generated compiler/build outputs, caches, local secrets and developer state. Imported source/evidence is staged from an explicit file allowlist, including archived files matched by historical nested ignores.
- `.gitattributes`: disables text conversion so imported bytes and historical line endings remain intact.
- `NOTICE.md`: preserves component license boundaries without imposing a blanket license.
- `provenance/source-inventory.json` and `provenance/exclusions.json`: imported file identities and explicit exclusion ledger.
- `provenance/PACKAGING.md`: this packaging change ledger.
- `scripts/repository_check.py`: packaging-only host verification runner. It verifies source identities and sealed evidence, makes disposable test copies, copies mutable module-cache inputs, and exercises the preserved tests and actual clean TinyGo/application rebuild with the pinned external SDK. It performs no new HIL, serial access, reset or flash.

The complete Phase 2 sealed archive and its original sidecars belong to the private prerelease asset set, not Git blobs. The immutable Phase 1 baseline archive is retained in Git together with its browsable selected source. No compiled TinyGo CLI, root Actions workflow, agent authentication state or publication cache is added to Git. Empty upstream submodule directories are not converted into gitlinks.

Preserved historical upstream whitespace is not reformatted. Historical reports and nested upstream CI configuration remain evidence/source, not new root-level CI or a claim of modern toolchain support. The supported experimental scope remains one cog, `scheduler=none`, `gc=none`.
