#!/usr/bin/env python3
"""Smart self-updater — keeps the code current WITHOUT clobbering local changes.

Called by the launchers on each start. It fetches the latest code from GitHub and does a
three-way-style merge using a hash manifest recorded at install/last-update:

  * a file you never touched  -> updated to the new version;
  * a file you edited (config.yaml, or any src file) -> PRESERVED as-is, and the new
    upstream version is saved next to it as ``<file>.update`` so you can adopt changes
    if you want;
  * new files -> added.

Your data/outputs/.venv are never touched, and only public code is fetched, so nothing
leaves the machine (HIPAA-safe). Config loading merges with in-code defaults, so an old,
preserved config.yaml still picks up any new settings automatically.

Set XON_NO_UPDATE=1 to freeze the current version entirely.

Exit codes: 0 = up to date / no restart needed; 10 = updated, launcher should restart;
anything else = skipped (e.g. offline) — the launcher just proceeds.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "Harshu-Pande/xon-aperiodic-pipeline"
ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(ROOT, ".xon_manifest.json")
VERSION = os.path.join(ROOT, ".xon_version")

EXCLUDE_DIRS = {".venv", "data", "outputs", ".git", "__pycache__", ".pytest_cache"}
EXCLUDE_NAMES = {".xon_version", ".xon_manifest.json"}
# files that are user working files, never overwritten even if unmodified-by-hash logic says so
NEVER_OVERWRITE_SUFFIX = (".update", ".bak", ".pyc")


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_files(base: str):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name in EXCLUDE_NAMES or name.endswith(NEVER_OVERWRITE_SUFFIX):
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, base)


def _fetch_latest_sha() -> str | None:
    url = f"https://api.github.com/repos/{REPO}/commits/main"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "xon-updater", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        return str(data.get("sha") or "") or None
    except Exception:
        return None


def _download_zip(dest: str) -> bool:
    url = f"https://github.com/{REPO}/archive/refs/heads/main.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "xon-updater"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
            shutil.copyfileobj(r, out)
        return True
    except Exception:
        return False


def _load_json(path: str) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _build_manifest(base: str) -> dict:
    return {rel: _sha(os.path.join(base, rel)) for rel in _rel_files(base)}


def smart_merge(newroot: str, root: str, manifest: dict):
    """Merge the freshly-downloaded tree (newroot) into the install (root), preserving any
    file the user edited. Mutates ``manifest`` in place and the filesystem. Returns
    (n_updated, [preserved_rel_paths])."""
    preserved, updated = [], 0
    for rel in _rel_files(newroot):
        new_file = os.path.join(newroot, rel)
        local_file = os.path.join(root, rel)
        new_sha = _sha(new_file)
        if not os.path.exists(local_file):                      # brand-new file
            os.makedirs(os.path.dirname(local_file) or ".", exist_ok=True)
            shutil.copy2(new_file, local_file)
            manifest[rel] = new_sha
            updated += 1
            continue
        local_sha = _sha(local_file)
        shipped_sha = manifest.get(rel)
        if local_sha == new_sha:                                # already identical
            manifest[rel] = new_sha
        elif shipped_sha is not None and local_sha != shipped_sha:
            # the user edited this file -> preserve it; drop the new version alongside
            if new_sha != shipped_sha:
                try:
                    shutil.copy2(new_file, local_file + ".update")
                except Exception:
                    pass
                preserved.append(rel)
            # keep manifest[rel] at the last shipped sha so upstream is still tracked
        else:                                                   # user did not touch it -> update
            shutil.copy2(new_file, local_file)
            manifest[rel] = new_sha
            updated += 1
    return updated, preserved


def main() -> int:
    if os.environ.get("XON_NO_UPDATE") == "1":
        return 0
    latest = _fetch_latest_sha()
    if not latest:
        return 0  # offline or rate-limited: just run what we have
    current = ""
    if os.path.exists(VERSION):
        try:
            current = open(VERSION).read().strip()
        except Exception:
            current = ""

    # First run after a fresh install (or missing manifest): record a baseline, don't re-download.
    if not current or not os.path.exists(MANIFEST):
        try:
            json.dump(_build_manifest(ROOT), open(MANIFEST, "w"))
            open(VERSION, "w").write(latest)
        except Exception:
            pass
        return 0

    if latest == current:
        return 0  # already up to date

    # --- download and smart-merge ---
    tmp = tempfile.mkdtemp(prefix="xon_update_")
    try:
        zpath = os.path.join(tmp, "u.zip")
        if not _download_zip(zpath):
            return 1
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(tmp)
        # find the extracted repo root (…-main)
        newroot = None
        for name in os.listdir(tmp):
            cand = os.path.join(tmp, name)
            if os.path.isdir(cand) and name.startswith("xon-aperiodic-pipeline"):
                newroot = cand
                break
        if not newroot:
            return 1

        manifest = _load_json(MANIFEST)
        updated, preserved = smart_merge(newroot, ROOT, manifest)
        try:
            json.dump(manifest, open(MANIFEST, "w"))
            open(VERSION, "w").write(latest)
        except Exception:
            pass

        if updated:
            print(f"Updated to the latest version ({updated} file(s) refreshed).")
        if preserved:
            print("Kept your local changes to: " + ", ".join(preserved))
            print("  (the newer versions were saved next to them as <file>.update)")
        return 10 if (updated or preserved) else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
