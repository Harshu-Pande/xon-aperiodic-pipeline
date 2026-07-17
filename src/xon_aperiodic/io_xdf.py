"""Load a Xon .xdf recording into an MNE Raw object.

The loader is deliberately forgiving: it auto-detects the EEG stream (scoring every
stream in the file), reads real electrode labels from the XDF metadata when present,
figures out the sampling rate from either the nominal rate or the timestamps, and
converts the stored units to Volts for MNE. All of this so a user can "just point it
at a file" and have it work, on any machine.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .logging_utils import step, info

try:
    import pyxdf
except ImportError as exc:  # pragma: no cover - environment guard
    raise ImportError(
        "This pipeline reads .xdf files and needs pyxdf. Install it with:\n"
        "  pip install pyxdf"
    ) from exc

import mne


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def unit_scale_to_volts(unit_name: str) -> float:
    """Return the multiplier that converts the given unit to Volts."""
    unit = str(unit_name).strip().lower().replace("μ", "u")
    if unit in {"v", "volt", "volts"}:
        return 1.0
    if unit in {"mv", "millivolt", "millivolts"}:
        return 1e-3
    if unit in {"uv", "microvolt", "microvolts"}:
        return 1e-6
    raise ValueError(f"Unknown data_units={unit_name!r}. Use 'uV', 'mV', or 'V'.")


def safe_name(text: str) -> str:
    """Make a file-safe subject/session label from a path or string."""
    text = Path(str(text)).stem
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "subject"


def _info_value(info_dict: Dict[str, Any], key: str, default: str = "") -> str:
    value = info_dict.get(key, [default])
    if isinstance(value, list) and len(value) > 0:
        return str(value[0])
    return str(value) if value is not None else default


def _nominal_srate(stream: Dict[str, Any]) -> float:
    raw_value = stream.get("info", {}).get("nominal_srate", [0])
    try:
        return float(raw_value[0] if isinstance(raw_value, list) else raw_value)
    except Exception:
        return 0.0


def _srate_from_timestamps(stream: Dict[str, Any]) -> float:
    ts = np.asarray(stream.get("time_stamps", []), dtype=float)
    if len(ts) < 3:
        return 0.0
    diffs = np.diff(ts)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if len(diffs) == 0:
        return 0.0
    return float(1.0 / np.median(diffs))


def _time_series_2d(stream: Dict[str, Any]) -> np.ndarray:
    data = np.asarray(stream.get("time_series", []))
    if data.ndim == 1:
        data = data[:, None]
    return data


def extract_channel_names(stream: Dict[str, Any], n_channels: int) -> List[str]:
    """Read channel labels from XDF metadata; fall back to Ch1..ChN. Names are
    made unique (MNE requires it)."""
    meta = stream.get("info", {})
    ch_names: List[str] = []
    try:
        channels = meta["desc"][0]["channels"][0]["channel"]
        for idx, ch in enumerate(channels, start=1):
            label = ""
            if isinstance(ch, dict):
                raw_label = ch.get("label", [""])
                label = str(raw_label[0]) if isinstance(raw_label, list) and raw_label else str(raw_label)
            ch_names.append(label.strip() or f"Ch{idx}")
    except Exception:
        pass

    if len(ch_names) != n_channels:
        ch_names = [f"Ch{i + 1}" for i in range(n_channels)]

    seen: Dict[str, int] = {}
    unique: List[str] = []
    for name in ch_names:
        base = name or "Ch"
        if base not in seen:
            seen[base] = 1
            unique.append(base)
        else:
            seen[base] += 1
            unique.append(f"{base}_{seen[base]}")
    return unique


# ---------------------------------------------------------------------------
# stream selection
# ---------------------------------------------------------------------------
def list_xdf_streams(path: str) -> List[Dict[str, Any]]:
    """Print (and return) a summary of the streams in a file, so a user can pick
    the right EEG stream if auto-detection guesses wrong."""
    streams, _ = pyxdf.load_xdf(path)
    info("\nXDF streams found:")
    summary = []
    for idx, stream in enumerate(streams):
        meta = stream.get("info", {})
        name = _info_value(meta, "name", "")
        stype = _info_value(meta, "type", "")
        nominal = _nominal_srate(stream)
        estimated = _srate_from_timestamps(stream)
        data = _time_series_2d(stream)
        shape = tuple(data.shape)
        info(f"  [{idx}] name={name!r}, type={stype!r}, nominal_srate={nominal:.3f}, "
             f"estimated_srate={estimated:.3f}, shape(samples, channels)={shape}")
        if data.ndim == 2 and data.shape[1] > 0:
            ch_names = extract_channel_names(stream, data.shape[1])
            preview = ch_names[:10]
            suffix = " ..." if len(ch_names) > 10 else ""
            info(f"      channels: {preview}{suffix}")
        summary.append(dict(index=idx, name=name, type=stype, nominal_srate=nominal,
                            estimated_srate=estimated, shape=shape))
    return summary


def _score_stream(stream: Dict[str, Any]) -> float:
    """Heuristic score for auto-choosing the EEG stream."""
    meta = stream.get("info", {})
    name = _info_value(meta, "name", "")
    stype = _info_value(meta, "type", "")
    combined = f"{name} {stype}".lower()
    data = _time_series_2d(stream)
    if data.size == 0 or data.shape[0] < 10:
        return -np.inf
    if any(w in combined for w in ["marker", "markers", "event", "trigger", "annotation"]):
        return -np.inf
    sfreq = _nominal_srate(stream) or _srate_from_timestamps(stream)
    n_channels, n_samples = data.shape[1], data.shape[0]
    score = 0.0
    if "eeg" in combined:
        score += 100.0
    if "xon" in combined:
        score += 25.0
    if 100 <= sfreq <= 2000:
        score += 25.0
    elif sfreq > 0:
        score += 5.0
    score += min(n_channels, 32) * 1.0
    score += min(n_samples / 10000.0, 20.0)
    return score


def choose_xdf_stream(streams: Sequence[Dict[str, Any]], stream_name: Optional[str] = None,
                      stream_type: Optional[str] = None) -> Dict[str, Any]:
    """Choose the EEG stream by explicit name/type, else by heuristic score."""
    if stream_name or stream_type:
        matches = []
        for stream in streams:
            meta = stream.get("info", {})
            name = _info_value(meta, "name", "")
            stype = _info_value(meta, "type", "")
            ok_name = True if stream_name is None else (name == stream_name)
            ok_type = True if stream_type is None else (stype == stream_type)
            if ok_name and ok_type:
                matches.append(stream)
        if not matches:
            available = [(_info_value(s.get("info", {}), "name", ""),
                         _info_value(s.get("info", {}), "type", "")) for s in streams]
            raise ValueError(
                f"No XDF stream matched stream_name={stream_name!r}, stream_type={stream_type!r}.\n"
                f"Available streams: {available}")
        if len(matches) > 1:
            info(f"  Warning: {len(matches)} streams matched; using the first.")
        return matches[0]

    scored = [(_score_stream(s), s) for s in streams]
    scored = [(sc, s) for sc, s in scored if np.isfinite(sc)]
    if not scored:
        raise ValueError("Could not automatically find a usable EEG stream. List the "
                         "streams (xon-pipeline streams <file>) and set xdf.stream_name/type.")
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


# ---------------------------------------------------------------------------
# the loader
# ---------------------------------------------------------------------------
def load_xdf_as_raw(path: str, data_units: str = "uV", stream_name: Optional[str] = None,
                    stream_type: Optional[str] = None) -> mne.io.RawArray:
    """Load the chosen XDF EEG stream into an MNE RawArray (data in Volts)."""
    step("STEP 1: Load Xon .xdf recording")
    info(f"  File: {path}")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Could not find XDF file: {path}")

    streams, _ = pyxdf.load_xdf(path)
    if not streams:
        raise ValueError("No streams found in this XDF file.")

    stream = choose_xdf_stream(streams, stream_name=stream_name, stream_type=stream_type)
    meta = stream.get("info", {})
    name = _info_value(meta, "name", "")
    stype = _info_value(meta, "type", "")

    data = _time_series_2d(stream)
    if data.size == 0 or data.shape[0] < 10:
        raise ValueError("Selected stream has no usable numeric samples.")

    n_samples, n_channels = data.shape
    ch_names = extract_channel_names(stream, n_channels)

    nominal = _nominal_srate(stream)
    estimated = _srate_from_timestamps(stream)
    sfreq = nominal if nominal > 0 else estimated
    if sfreq <= 0:
        raise ValueError("Could not determine sampling rate from the selected XDF stream.")

    ts = np.asarray(stream.get("time_stamps", []), dtype=float)
    if len(ts) > 3:
        diffs = np.diff(ts)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if len(diffs) > 0:
            jitter_ms = float(np.std(diffs) * 1000.0)
            if jitter_ms > 2.0:
                info(f"  Warning: timestamp jitter is {jitter_ms:.2f} ms. RawArray uses a "
                     "regular sampling grid based on sfreq.")

    scale = unit_scale_to_volts(data_units)
    data_v = np.asarray(data, dtype=float).T * scale

    mne_info = mne.create_info(ch_names=ch_names, sfreq=float(sfreq), ch_types=["eeg"] * n_channels)
    raw = mne.io.RawArray(data_v, mne_info, verbose=False)

    info(f"  XDF stream used: name={name!r}, type={stype!r}")
    info(f"  Sampling rate: {sfreq:.3f} Hz")
    if nominal > 0 and estimated > 0:
        info(f"  Nominal/estimated sfreq: {nominal:.3f}/{estimated:.3f} Hz")
    info(f"  Duration: {raw.times[-1]:.1f} sec ({raw.times[-1] / 60:.2f} min)")
    info(f"  Channels ({len(raw.ch_names)}): {raw.ch_names}")
    info(f"  Data unit assumed: {data_units} -> converted to Volts for MNE")
    return raw
