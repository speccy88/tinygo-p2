#!/usr/bin/env python3
"""Strict, dependency-free sanity checks; not a proof of P2 codegen correctness."""
from __future__ import annotations
import hashlib
import re
import struct
from pathlib import Path

class CheckError(ValueError):
    pass

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_ir(text: str, exports: tuple[str, ...] = ('p2_add','p2_mix')) -> dict:
    if not re.search(r'^target triple = "p2(?:-[^"]*)?"$', text, re.M):
        raise CheckError("IR is not explicitly targeted at P2")
    definitions = re.findall(r'^define\s+([^\n]+)\{', text, re.M)
    names = []
    for definition in definitions:
        m = re.search(r'\bi32\s+@(p2_add|p2_mix)\(([^)]*)\)', definition)
        if not m or re.search(r'\b(?:fastcc|coldcc|swiftcc|cc\s+\d+)\b', definition):
            raise CheckError("unexpected function signature/calling convention")
        params = [x.strip() for x in m.group(2).split(',')]
        if len(params) != 2 or any(not re.match(r'^i32\b', p) for p in params):
            raise CheckError("export does not have exactly two i32 parameters")
        names.append(m.group(1))
    if sorted(names) != sorted(exports):
        raise CheckError("expected exactly the selected scalar exports")
    if re.search(r'^declare\b|\b(?:call|invoke|callbr)\b', text, re.M):
        raise CheckError("leaf proof contains a call or declaration")
    if re.search(r'^@[^\n]*=', text, re.M):
        raise CheckError("leaf proof unexpectedly depends on globals")
    if '"no-jump-tables"="true"' not in text:
        raise CheckError("no-jump-tables attribute missing")
    if not re.search(r'\badd\s+i32\b', text):
        raise CheckError("addition absent from generated IR")
    return {'exports': names, 'target': 'p2', 'runtime_calls': 0}

def check_elf(path: Path, expected_type: int, require_exports: bool, exports: tuple[str, ...] = ('p2_add','p2_mix')) -> dict:
    data = path.read_bytes()
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise CheckError("not an ELF32 little-endian version-1 artifact")
    h = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    _, typ, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, shstr = h
    if typ != expected_type or machine != 300 or version != 1 or ehsize != 52:
        raise CheckError(f"wrong ELF identity: type={typ}, machine={machine}; expected EM_P2=300")
    if shnum == 0 or shsize != 40 or shoff + shnum * shsize > len(data):
        raise CheckError("missing/invalid section table")
    sections = [struct.unpack_from('<10I', data, shoff + i * shsize) for i in range(shnum)]
    def section_bytes(i: int) -> bytes:
        if i >= len(sections): raise CheckError("bad section link")
        s = sections[i]
        if s[1] == 8: return b''  # SHT_NOBITS
        if s[4] + s[5] > len(data): raise CheckError("section extends beyond file")
        return data[s[4]:s[4]+s[5]]
    def string_at(strings: bytes, start: int) -> str:
        if start >= len(strings): raise CheckError("bad symbol string offset")
        end = strings.find(b'\x00', start)
        if end < 0: raise CheckError("unterminated symbol name")
        return strings[start:end].decode('utf-8', 'strict')
    defined = {}
    undefined = []
    for i, s in enumerate(sections):
        section_bytes(i)
        if s[1] != 2: continue  # SHT_SYMTAB
        if s[9] != 16 or s[5] % 16: raise CheckError("bad symbol-table entry size")
        strings = section_bytes(s[6])
        symbols = section_bytes(i)
        for off in range(0, len(symbols), 16):
            nameoff, value, size, info, other, index = struct.unpack_from('<IIIBBH', symbols, off)
            name = string_at(strings, nameoff)
            if not name: continue
            if index == 0:
                undefined.append(name)
            elif name in ('p2_add', 'p2_mix'):
                if (info >> 4) != 1 or (info & 15) != 2 or size == 0 or index >= shnum:
                    raise CheckError(f"{name} is not a nonempty global function")
                body = sections[index]
                relative = value if typ == 1 else value - body[3]
                if relative < 0 or relative + size > body[5] or not (body[2] & 4):
                    raise CheckError(f"{name} has an invalid executable section range")
                if name in defined: raise CheckError("duplicate export")
                defined[name] = {'value': value, 'size': size, 'section': index}
    if typ == 1 and undefined:
        raise CheckError(f"standalone scalar object has unresolved dependencies: {undefined}")
    if require_exports and set(defined) != set(exports):
        raise CheckError("Go exports are absent from ELF symbol table")
    loads = []
    if typ == 2:
        if not phnum or phsize != 32 or phoff + phnum * phsize > len(data):
            raise CheckError("executable has no valid program headers")
        for i in range(phnum):
            p = struct.unpack_from('<8I', data, phoff + phsize * i)
            if p[0] != 1: continue
            _, offset, vaddr, paddr, filesz, memsz, pflags, align = p
            if filesz > memsz or offset + filesz > len(data) or vaddr + memsz > 0x7c000:
                raise CheckError("load segment exceeds usable internal HUB RAM or file")
            if paddr != vaddr:
                raise CheckError("unexpected physical/virtual address mapping")
            loads.append({'address': vaddr, 'filesz': filesz, 'memsz': memsz})
        if not loads or not any(p['address'] <= entry < p['address'] + p['memsz'] for p in loads):
            raise CheckError("entry point not in a loadable segment")
    return {'sha256': sha256(path), 'bytes': len(data), 'elf_type': typ,
            'machine': machine, 'entry': entry, 'exports': defined, 'load_segments': loads}
