#!/usr/bin/env python3
"""Atomically apply the explicit, identity-pinned Phase 2 patches.

No checkout is mutated until every declared patch byte, checkout revision, module
identity, path scope, and complete intended-file pre/postimage has been checked.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def out(cmd, cwd):
    return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def resolve(manifest, value):
    path = Path(value)
    return path if path.is_absolute() else (manifest.parent / path).resolve()


def applies(checkout, patch, reverse=False):
    command = ['git', 'apply', '--check'] + (['--reverse'] if reverse else []) + [str(patch)]
    return subprocess.run(command, cwd=checkout, capture_output=True, text=True).returncode == 0


def patch_paths(patch):
    """Return the complete declared path scope from git diff headers."""
    result = []
    for line in patch.read_text(encoding='utf-8').splitlines():
        if not line.startswith('diff --git a/'):
            continue
        fields = line.split()
        if len(fields) != 4 or not fields[2].startswith('a/') or not fields[3].startswith('b/'):
            raise ValueError('malformed diff header')
        before, after = fields[2][2:], fields[3][2:]
        if before != after or not before or Path(before).is_absolute() or '..' in Path(before).parts:
            raise ValueError('unsafe or rename diff path')
        result.append(before)
    if not result or len(result) != len(set(result)):
        raise ValueError('missing or duplicate diff paths')
    return result


def identities(item):
    files = item.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('missing complete intended-file identities')
    answer = {}
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {'path', 'before_sha256', 'after_sha256'}:
            raise ValueError('invalid intended-file identity')
        path = entry['path']
        if not isinstance(path, str) or not path or Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('unsafe intended-file path')
        if not all(isinstance(entry[key], str) and SHA256.fullmatch(entry[key]) for key in ('before_sha256', 'after_sha256')):
            raise ValueError('noncanonical intended-file digest')
        if path in answer:
            raise ValueError('duplicate intended-file identity')
        answer[path] = entry
    return answer


def checked_file_bytes(checkout, path, status):
    # Check the live working tree in both states: git apply deliberately permits
    # unrelated dirty bytes outside a hunk, which is not acceptable here.
    return (checkout / path).read_bytes()


def validate_module_identity(manifest, data):
    # Schema 2 manifests pin TinyGo's local go-llvm binding rather than relying
    # on a potentially modified global module cache. Schema 1 remains accepted
    # solely for the supplied isolated compatibility fixtures.
    if data.get('schema', 1) < 2:
        return
    module = data.get('module_identity')
    if not isinstance(module, dict) or not module:
        raise ValueError('missing pinned module identity')
    for rel, wanted in module.items():
        if not isinstance(rel, str) or not isinstance(wanted, str) or not SHA256.fullmatch(wanted):
            raise ValueError('invalid module identity')
        path = resolve(manifest, rel)
        if not path.is_file() or sha(path) != wanted:
            raise ValueError('pinned module identity mismatch: ' + rel)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    data = json.loads(manifest_path.read_text())
    try:
        validate_module_identity(manifest_path, data)
        patches = data['patches']
        if not isinstance(patches, list) or len(patches) != 3:
            raise ValueError('expected exactly three declared patches')
        prepared = []
        for item in patches:
            checkout, patch = resolve(manifest_path, item['checkout']), resolve(manifest_path, item['patch'])
            if not (checkout / '.git').is_dir() or not patch.is_file():
                raise ValueError('missing checkout or patch for ' + str(item.get('name')))
            if not SHA256.fullmatch(item.get('patch_sha256', '')) or sha(patch) != item['patch_sha256']:
                raise ValueError('patch bytes mismatch for ' + str(item.get('name')))
            declared = identities(item)
            if set(patch_paths(patch)) != set(declared):
                raise ValueError('undeclared or missing patch path for ' + str(item.get('name')))
            head = out(['git', 'rev-parse', 'HEAD'], checkout)
            if head != item.get('before_head'):
                raise ValueError('wrong pinned revision for ' + str(item.get('name')))
            if applies(checkout, patch):
                status = 'fresh'
            elif applies(checkout, patch, reverse=True):
                status = 'already'
            else:
                raise ValueError('patch neither applies nor reverses for ' + str(item.get('name')))
            for path, identity in declared.items():
                actual = checked_file_bytes(checkout, path, status)
                expected = identity['before_sha256'] if status == 'fresh' else identity['after_sha256']
                if sha_bytes(actual) != expected:
                    raise ValueError('intended-file identity mismatch for ' + str(item.get('name')) + ':' + path)
            prepared.append((item, checkout, patch, head, status))
    except (KeyError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit('unexpected-content: ' + str(exc))

    records = []
    for item, checkout, patch, before, status in prepared:
        if status == 'fresh':
            subprocess.run(['git', 'apply', '--whitespace=nowarn', str(patch)], cwd=checkout, check=True)
        records.append({'name': item['name'], 'status': status, 'checkout': str(checkout),
                        'before_head': before, 'after_head': out(['git', 'rev-parse', 'HEAD'], checkout),
                        'patch_sha256': sha(patch),
                        'tree_diff_sha256': sha_bytes(out(['git', 'diff', '--binary', 'HEAD'], checkout).encode())})
    result = {'status': 'PASS', 'manifest_sha256': sha(manifest_path), 'patches': records}
    encoded = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
