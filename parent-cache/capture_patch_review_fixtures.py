#!/usr/bin/env python3
"""Capture real-patch test fixtures read-only from Phase2 source checkouts.

Run inside the build container: python3 this_file.py /path/to/.work/phase2
The emitted JSON is a test input, not proof that a synthesized go-llvm Git HEAD
is an upstream revision. Verify the pinned module ZIP independently.
"""
import argparse
import json
from pathlib import Path
import subprocess


def capture(root):
    manifest = json.loads((root / 'patch-manifest.json').read_text())
    result = []
    for item in manifest['patches']:
        text = Path(item['patch']).read_text()
        paths = [line[6:].split()[0] for line in text.splitlines()
                 if line.startswith('--- a/')]
        assert paths and len(paths) == len(set(paths))
        assert all(not Path(p).is_absolute() and '..' not in Path(p).parts
                   for p in paths)
        files = {p: subprocess.check_output(['git', 'show', 'HEAD:' + p],
                                           cwd=item['checkout'], text=True)
                 for p in paths}
        result.append({'name': item['name'], 'source_head': item['before_head'],
                       'patch': text, 'files': files})
    assert len(result) == 3
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(args.root), indent=2))
