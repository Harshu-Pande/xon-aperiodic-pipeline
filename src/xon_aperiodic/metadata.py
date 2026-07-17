"""Figure out each file's participant / session / condition.

Strategy (both configurable in config.yaml, never in code):
  1. Parse the file NAME with the regex patterns in ``metadata.patterns``.
  2. If a ``metadata.manifest`` CSV is provided, its rows OVERRIDE / fill in the
     parsed values (matched by file name or stem).

This is what makes the repo robust to future naming changes: if the lab renames
files, you edit one regex here or drop in a manifest - the pipeline code is untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .config import Config
from .logging_utils import info


@dataclass
class FileMetadata:
    """Everything we can say about a recording before analysing it."""
    path: str
    file_stem: str
    participant: str = ""
    session: str = ""
    condition: str = "unknown"
    subject_id: str = ""     # unique, file-safe label used for output naming

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


def _apply_pattern(name: str, pattern: Optional[str]) -> Optional[str]:
    if not pattern:
        return None
    m = re.search(pattern, name, flags=re.IGNORECASE)
    if not m:
        return None
    # Prefer the first capturing group; else the whole match.
    return (m.group(1) if m.groups() else m.group(0)).strip()


def _format_participant(value: Optional[str], cfg: Config) -> str:
    if not value:
        return ""
    prefix = str(cfg.get("metadata", "participant_prefix", "") or "")
    pad = int(cfg.get("metadata", "participant_zero_pad", 0) or 0)
    if value.isdigit() and pad > 0:
        return f"{prefix}{int(value):0{pad}d}"
    # already has a prefix / non-numeric id -> keep as-is (uppercased for consistency)
    return value.upper()


def _canon_condition(value: Optional[str], cfg: Config) -> str:
    if not value:
        return "unknown"
    aliases = {k.lower(): v for k, v in (cfg.section("metadata").get("condition_aliases") or {}).items()}
    return aliases.get(value.lower(), value.lower())


def _load_manifest(cfg: Config) -> Optional[pd.DataFrame]:
    manifest = cfg.get("metadata", "manifest", None)
    if not manifest:
        return None
    path = cfg.resolve_path(str(manifest))
    if not path.exists():
        info(f"  Manifest {path} not found; using filename parsing only.")
        return None
    df = pd.read_csv(path, dtype=str).fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    if "file" not in df.columns:
        info("  Manifest has no 'file' column; ignoring it.")
        return None
    info(f"  Loaded manifest with {len(df)} row(s): {path.name}")
    return df


class MetadataResolver:
    """Resolves metadata for files, applying patterns then an optional manifest."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.patterns = cfg.section("metadata").get("patterns", {})
        self.manifest = _load_manifest(cfg)
        self._used_ids: Dict[str, int] = {}

    def _manifest_row(self, path: Path) -> Dict[str, str]:
        if self.manifest is None:
            return {}
        stem, name = path.stem.lower(), path.name.lower()
        for _, row in self.manifest.iterrows():
            key = str(row.get("file", "")).strip().lower()
            if key and key in {stem, name, Path(key).stem.lower()}:
                return {k: str(v).strip() for k, v in row.items() if k != "file" and str(v).strip()}
        return {}

    def resolve(self, path: str | Path) -> FileMetadata:
        path = Path(path)
        name = path.name

        participant = _format_participant(_apply_pattern(name, self.patterns.get("participant")), self.cfg)
        session = _apply_pattern(name, self.patterns.get("session")) or ""
        condition = _canon_condition(_apply_pattern(name, self.patterns.get("condition")), self.cfg)

        # Manifest overrides parsed values.
        row = self._manifest_row(path)
        if row.get("participant"):
            participant = _format_participant(row["participant"], self.cfg)
        if row.get("session"):
            session = row["session"]
        if row.get("condition"):
            condition = _canon_condition(row["condition"], self.cfg)

        subject_id = self._make_unique_id(path, participant, session, condition)
        return FileMetadata(path=str(path), file_stem=path.stem, participant=participant,
                            session=session, condition=condition, subject_id=subject_id)

    def _make_unique_id(self, path: Path, participant: str, session: str, condition: str) -> str:
        parts = [p for p in [participant, (f"S{session}" if session else ""),
                             (condition if condition != "unknown" else "")] if p]
        base = "_".join(parts) if parts else re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem)
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_") or "subject"
        # de-duplicate if two files map to the same label
        if base in self._used_ids:
            self._used_ids[base] += 1
            return f"{base}_{self._used_ids[base]}"
        self._used_ids[base] = 1
        return base
