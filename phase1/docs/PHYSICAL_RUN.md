# Physical P2 run (RAM-only)

Run project commands only through the `propeller2` container. The verified target is the P2-EC32MB Rev B with 20 MHz TCXO, console `/dev/ttyUSB0` (FTDI `0403:6001`, serial `A500507h`), 115200 baud. Do not run a download while the board controls equipment.

## Reproducible least-privilege container

The currently verified image is `local/propeller2-tinygo-dev:0.23.0-p2` (`sha256:ba28be8aa42cbd961c6796fb08fcad02d32e96fb9ee4af8c805636243908dac6`). It runs as `10000:10000`, group `18`, with only `/dev/ttyUSB0:rw`, no network, all capabilities dropped, `no-new-privileges`, 5 GiB memory / 6 GiB memory+swap, and 2 CPUs. It has no Docker socket and is not privileged.

Before recreation, inspect the container and confirm it has no active worker or serial-holder process. Do **not** force-remove it and do not kill a serial holder. The commands below recreate only the named container:

```sh
docker inspect propeller2
docker stop propeller2
docker rm propeller2
docker run -d --name propeller2 --network none --init --user 10000:10000 --group-add 18 \
  --cap-drop ALL --security-opt no-new-privileges:true --memory 5g --memory-swap 6g --cpus 2 \
  --device /dev/ttyUSB0:/dev/ttyUSB0:rw \
  -v /DATA/AppData/hopeful_renaud/propeller2:/work/propeller2 \
  local/propeller2-tinygo-dev:0.23.0-p2 sleep infinity
docker exec propeller2 sh -lc 'id; stat -c "%n %a %u:%g" /dev/ttyUSB0'
```

The exact image recipe is included as `artifacts/Dockerfile.tinygo-p2-dev`.

## Verified build and RAM-only gates

```sh
# These docker exec commands can run from any directory on the Docker host.
# Hermes sees /opt/data/propeller2/tinygo-p2-handoff; the daemon-host bind is
# /DATA/AppData/hopeful_renaud/propeller2 -> /work/propeller2 inside this container.
# Keep the pinned compatibility Go on PATH for host checks.
docker exec -w /work/propeller2/tinygo-p2-handoff propeller2 sh -lc \
  'export PATH=/work/propeller2/tinygo-p2-handoff/.work/toolchains/go1.18.10/bin:$PATH; make host-test'
docker exec -w /work/propeller2/tinygo-p2-handoff propeller2 sh -lc \
  'export P2_JOBS=2; make probe-full && make baseline && make firmware'
# These are the only commands that download/reset the board; each is RAM-only.
docker exec -w /work/propeller2/tinygo-p2-handoff propeller2 \
  python3 scripts/project.py hil --mode c --port /dev/ttyUSB0 --allow-ram-reset --random 128
docker exec -w /work/propeller2/tinygo-p2-handoff propeller2 \
  python3 scripts/project.py hil --mode go --port /dev/ttyUSB0 --allow-ram-reset --random 128
# For the original full gate, repeat the final Go command twice more (three fresh Go loads total).
docker exec -w /work/propeller2/tinygo-p2-handoff propeller2 python3 scripts/project.py evidence
```

`hil` alone owns serial/DTR. It uses pinned `.work/bin/loadp2`, `-ZERO`, and an ELF payload. Do not open the device separately, toggle DTR, add `-9`, use `@address`, or write flash, SD, PSRAM, or non-console GPIO.

`stdin->_flag &= ~_IOCOOKED` is compiled only for the P2 target path after UART initialization. The pinned P2 libc otherwise echoes the strict binary-protocol input; host tests intentionally exclude this P2-specific libc field access.
