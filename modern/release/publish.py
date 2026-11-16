#!/usr/bin/env python3
"""Upload a verified GitHub draft release, then publish it explicitly.

Uses the existing Git credential helper in memory; never writes a token to disk.
Run `stage` first, inspect its verified result, then run `publish` with the same
arguments. An existing published release is never edited by this helper.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "publish", "verify"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    args = parser.parse_args()
    if len(args.repo.split("/")) != 2 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./" for c in args.repo):
        raise ValueError("Expected owner/repository")
    credential = subprocess.run(["git", "credential", "fill"],
        input=f"protocol=https\nhost=github.com\npath={args.repo}.git\n\n",
        text=True, capture_output=True, check=True)
    fields = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
    token = fields["password"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tinygo-p2-release"}
    base = f"https://api.github.com/repos/{args.repo}"

    def api(path, method="GET", data=None):
        payload = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(base + path, data=payload, method=method,
            headers=dict(headers, **({"Content-Type": "application/json"} if payload else {})))
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    assets = {}
    for line in (args.assets_dir / "SHA256SUMS").read_text().splitlines():
        expected, filename = line.split(maxsplit=1)
        filename = filename.strip()
        if Path(filename).name != filename:
            raise ValueError("Asset paths must be simple filenames")
        path = args.assets_dir / filename
        if sha(path) != expected:
            raise ValueError(f"Local checksum mismatch: {filename}")
        assets[filename] = expected
    assets["SHA256SUMS"] = sha(args.assets_dir / "SHA256SUMS")
    try:
        release = api("/releases/tags/" + urllib.parse.quote(args.tag, safe=""))
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        # GitHub's tag endpoint omits drafts, even for their owner. The releases
        # collection includes them for an authenticated user with write access.
        release = None
        page = 1
        while release is None:
            candidates = api(f"/releases?per_page=100&page={page}")
            release = next((item for item in candidates if item["tag_name"] == args.tag), None)
            if len(candidates) < 100:
                break
            page += 1
        if release is None:
            if args.action != "stage":
                raise RuntimeError(f"No release exists for {args.tag}") from None
            release = api("/releases", "POST", {"tag_name": args.tag,
                "target_commitish": args.commit, "name": "TinyGo for Propeller 2 v0.1.0 — eight cogs, ready to try",
                "body": args.notes.read_text(encoding="utf-8"), "draft": True, "prerelease": False})
    if release["target_commitish"] != args.commit:
        raise ValueError("Release target does not match the supplied commit")
    if args.action != "verify" and not release["draft"]:
        raise ValueError("Refusing to modify an already published release")
    release_path = f"/releases/{release['id']}"
    if args.action == "stage":
        existing = {asset["name"]: asset for asset in release["assets"]}
        for name, expected in assets.items():
            if name in existing:
                if existing[name].get("digest") != f"sha256:{expected}":
                    raise ValueError(f"Existing remote asset differs: {name}")
                continue
            path = args.assets_dir / name
            endpoint = urllib.parse.urlsplit(release["upload_url"].split("{")[0])
            if endpoint.hostname != "uploads.github.com":
                raise ValueError("Unexpected upload host")
            connection = http.client.HTTPSConnection(endpoint.hostname, timeout=120)
            connection.putrequest("POST", endpoint.path + "?" + urllib.parse.urlencode({"name": name}))
            for key, value in dict(headers, **{"Content-Type": "application/octet-stream", "Content-Length": str(path.stat().st_size)}).items():
                connection.putheader(key, value)
            connection.endheaders()
            print(f"Uploading {name} ({path.stat().st_size:,} bytes)", flush=True)
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    connection.send(chunk)
            response = connection.getresponse()
            result = json.loads(response.read())
            connection.close()
            if response.status != 201 or result.get("digest") != f"sha256:{expected}":
                raise RuntimeError(f"Upload failed or digest mismatch: {name}, HTTP {response.status}")
            print(f"Verified remote SHA-256: {name}", flush=True)
    release = api(release_path)
    remote = {asset["name"]: asset for asset in release["assets"]}
    if set(remote) != set(assets):
        raise ValueError("Remote asset set differs from the verified local set")
    for name, expected in assets.items():
        if remote[name].get("digest") != f"sha256:{expected}" or remote[name]["state"] != "uploaded":
            raise ValueError(f"Remote asset failed verification: {name}")
    if args.action == "publish":
        release = api(release_path, "PATCH", {"draft": False, "make_latest": "true"})
    print(json.dumps({"url": release["html_url"], "draft": release["draft"],
                      "tag": release["tag_name"], "commit": release["target_commitish"],
                      "assets": [{"name": a["name"], "size": a["size"], "digest": a["digest"]}
                                 for a in release["assets"]]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
