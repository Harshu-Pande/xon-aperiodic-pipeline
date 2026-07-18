"""Tests for the change-preserving auto-updater's merge logic."""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("xon_update", ROOT / "update.py")
up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(up)


def _w(base, rel, txt):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt)


def test_smart_merge_preserves_user_edits(tmp_path):
    install = tmp_path / "install"
    upstream = tmp_path / "upstream"
    for rel, txt in [("config/config.yaml", "fooof: [1,40]\n"), ("src/a.py", "v1a\n"),
                     ("src/b.py", "v1b\n"), ("README.md", "v1\n")]:
        _w(install, rel, txt)
        _w(upstream, rel, txt)
    manifest = up._build_manifest(str(install))          # baseline recorded at install

    # user edits config + a.py locally
    _w(install, "config/config.yaml", "fooof: [15,50]\n")
    _w(install, "src/a.py", "USER EDIT\n")
    # upstream changes everything and adds a new file
    _w(upstream, "config/config.yaml", "fooof: [1,40]\nnew: true\n")
    _w(upstream, "src/a.py", "v2a\n")
    _w(upstream, "src/b.py", "v2b\n")
    _w(upstream, "README.md", "v2\n")
    _w(upstream, "src/c.py", "new file\n")

    updated, preserved = up.smart_merge(str(upstream), str(install), manifest)

    # user edits preserved
    assert (install / "config/config.yaml").read_text() == "fooof: [15,50]\n"
    assert (install / "src/a.py").read_text() == "USER EDIT\n"
    # new upstream versions offered alongside
    assert (install / "config/config.yaml.update").exists()
    assert (install / "src/a.py.update").read_text() == "v2a\n"
    # untouched files updated; new file added
    assert (install / "src/b.py").read_text() == "v2b\n"
    assert (install / "README.md").read_text() == "v2\n"
    assert (install / "src/c.py").read_text() == "new file\n"
    assert set(preserved) == {"src/a.py", "config/config.yaml"}
    assert updated == 3


def test_smart_merge_clean_update(tmp_path):
    """No local edits -> everything updates."""
    install = tmp_path / "install"; upstream = tmp_path / "upstream"
    _w(install, "src/a.py", "v1\n"); _w(upstream, "src/a.py", "v2\n")
    manifest = up._build_manifest(str(install))
    updated, preserved = up.smart_merge(str(upstream), str(install), manifest)
    assert (install / "src/a.py").read_text() == "v2\n"
    assert preserved == [] and updated == 1
