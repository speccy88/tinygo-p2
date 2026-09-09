# Authoring validation — TinyGo/P2 arithmetic proof

**Status: host checks passed; compiler integration and real hardware remain untested.**

| Check | Result | Scope |
|---|---|---|
| Python automated tests | 36 passed | Protocol, IR/ELF checker fixtures, negative controls and guard checks |
| Go automated tests | 3 passed | Standard Go, including 10,000 randomized arithmetic pairs and edge cases |
| Serial protocol integration | 138 challenges passed | Host-compiled C baseline through a pseudo-terminal, not a P2 board |
| Go overlay syntax/format | Passed | gofmt; not a TinyGo/LLVM typecheck or link |
| TinyGo 0.23 compiler hook + custom LLVM | NOT RUN | Requires building the pinned compiler stack |
| P2 object or ELF generation | NOT RUN | No P2 compiler binary was available in the authoring environment |
| Native macOS arm64 execution | NOT RUN | Authoring host was Linux x86-64 |
| USB serial and physical P2 execution | NOT RUN | Must be performed on the user's Mac and connected board |

The 138 serial challenges are part of the Python integration tests, not an additional claim of 138 unit tests. Each challenge checks an addition result and an order-sensitive bitwise/arithmetic result.

The host tests include deliberately wrong image identity and missing Go definitions, so a C-only baseline is not accepted as Go evidence. Synthetic ELF/IR fixtures exercise the validators; they are not generated P2 machine code.

## Evidence

- `host-validation.json`: commands, return codes, host version and explicit exclusions.
- `host-check-1.txt`: raw Python test output.
- `host-check-2.txt`: raw Go test output.
- `host-check-3.txt`: gofmt output (empty on success).
- `host-run-console.txt`: combined host-check execution output.
- `authoring-preflight.txt`: authoring environment details.

The authoring container could not resolve GitHub for source downloads. Source inspection was performed through repository tools; it does not substitute for building the TinyGo/LLVM combination.

No claim is made that most of the compiler integration is already finished. The prepared work consists of the source audit, pinned build workflow, proposed TinyGo compiler hook, C serial harness, host-side validation and explicit Codex acceptance contract.
