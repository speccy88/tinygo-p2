#!/usr/bin/env python3
"""PTY transport for one loadp2 process: no second serial open/DTR transition."""
from __future__ import annotations
import errno
import json
import os
import pty
import re
import secrets
import select
import signal
import subprocess
import time
import tty
from pathlib import Path

MASK = 0xffffffff
EDGE_CASES = [(0,0), (1,2), (0xffffffff,1), (0xffffffff,0xffffffff),
              (0x7fffffff,1), (0x80000000,0x80000000), (0,0xffffffff),
              (0x12345678,0x87654321), (0xaaaaaaaa,0x55555555), (7,3)]

class ProtocolError(RuntimeError):
    pass

def oracle(a: int, b: int) -> tuple[int, int]:
    x = (a ^ b) & MASK
    rotated = ((x << 5) | (x >> 27)) & MASK
    return (a+b) & MASK, (rotated+a-b) & MASK

def make_vectors(random_count: int = 128) -> list[dict]:
    if not 0 <= random_count <= 4096: raise ValueError("invalid vector count")
    pairs = EDGE_CASES + [(secrets.randbits(32), secrets.randbits(32)) for _ in range(random_count)]
    ids = set()
    vectors = []
    for a, b in pairs:
        nonce = secrets.randbits(32)
        while nonce in ids: nonce = secrets.randbits(32)
        ids.add(nonce)
        s, m = oracle(a, b)
        vectors.append({'id': nonce, 'a': a, 'b': b, 'sum': s, 'mix': m})
    return vectors

def request(v: dict) -> bytes:
    return f"Q {v['id']:08x} {v['a']:08x} {v['b']:08x}\r".encode('ascii')

def verify_response(line: bytes, mode: str, v: dict) -> dict:
    match = re.fullmatch(rb'R ([CG]) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8})', line.strip())
    if not match: raise ProtocolError(f"malformed response: {line!r}")
    got_mode = match[1].decode('ascii')
    got = [int(match[i], 16) for i in (2,3,4)]
    if got_mode != mode: raise ProtocolError(f"wrong image mode {got_mode}; expected {mode}")
    if got != [v['id'], v['sum'], v['mix']]:
        raise ProtocolError(f"mismatched nonce/result: got {got}, expected {[v['id'],v['sum'],v['mix']]}")
    return {'id': got[0], 'sum': got[1], 'mix': got[2], 'mode': got_mode}

class Terminal:
    def __init__(self, command: list[str], raw_log: Path):
        self.command = command
        self.log = raw_log.open('wb')
        self.master, slave = pty.openpty()
        tty.setraw(slave)
        try:
            self.proc = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                                         close_fds=True, start_new_session=True)
        except BaseException:
            os.close(self.master); self.log.close(); raise
        finally:
            os.close(slave)
        self.buffer = bytearray()
    def send(self, data: bytes):
        view = memoryview(data)
        while view:
            n = os.write(self.master, view)
            view = view[n:]
    def line(self, deadline: float) -> bytes:
        while True:
            for i, value in enumerate(self.buffer):
                if value in (10, 13):
                    result = bytes(self.buffer[:i]); del self.buffer[:i+1]
                    return result
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise ProtocolError("timeout waiting for device output")
            if not select.select([self.master], [], [], min(remaining, 0.25))[0]:
                if self.proc.poll() is not None: raise ProtocolError(f"loader exited with {self.proc.returncode}")
                continue
            try: data = os.read(self.master, 4096)
            except OSError as exc:
                if exc.errno == errno.EIO: raise ProtocolError("terminal closed unexpectedly") from exc
                raise
            if not data: raise ProtocolError("terminal reached EOF")
            self.log.write(data); self.log.flush(); self.buffer.extend(data)
            if len(self.buffer) > 1024*1024: raise ProtocolError("unbounded terminal output")
    def close(self):
        try:
            if self.proc.poll() is None:
                os.killpg(self.proc.pid, signal.SIGTERM)
                try: self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.proc.pid, signal.SIGKILL); self.proc.wait(timeout=2)
        finally:
            os.close(self.master); self.log.close()

def exchange(command: list[str], mode: str, vectors: list[dict], directory: Path,
             boot_timeout: float = 60, response_timeout: float = 3) -> dict:
    """Transport test only. The caller must establish artifact/hardware provenance."""
    if mode not in ('C', 'G'): raise ValueError("invalid image mode")
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'vectors.json').write_text(json.dumps(vectors, indent=2)+'\n')
    (directory/'command.json').write_text(json.dumps(command, indent=2)+'\n')
    result = {'status': 'FAIL', 'scope': 'transport-only', 'expected_mode': mode, 'passed': 0, 'total': len(vectors)}
    terminal = None
    try:
        terminal = Terminal(command, directory/'terminal.raw')
        deadline = time.monotonic()+boot_timeout
        while True:
            line = terminal.line(deadline).strip()
            if line.startswith(b'READY '):
                if line != f'READY {mode} 1'.encode(): raise ProtocolError(f"unexpected firmware: {line!r}")
                break
        with (directory/'responses.jsonl').open('w') as log:
            for v in vectors:
                terminal.send(request(v))
                deadline = time.monotonic()+response_timeout
                while True:
                    line = terminal.line(deadline).strip()
                    if not line: continue
                    if line.startswith(b'ERR '): raise ProtocolError(f"device rejected input: {line!r}")
                    if line.startswith(b'R '): break
                    raise ProtocolError(f"unexpected output during challenge: {line!r}")
                reply = verify_response(line, mode, v)
                log.write(json.dumps(reply)+'\n'); log.flush()
                result['passed'] += 1
        result['status'] = 'PASS'
        return result
    except BaseException as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if terminal is not None: terminal.close()
        (directory/'transport.json').write_text(json.dumps(result, indent=2)+'\n')
