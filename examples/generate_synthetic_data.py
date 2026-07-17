"""Generate synthetic Xon-like .xdf recordings with a KNOWN aperiodic exponent.

Real Xon data is HIPAA-protected and lives on a secure machine, so we validate the
pipeline against synthetic ground truth instead. This module (a) writes valid XDF
files pyxdf can read back, and (b) builds a small demo cohort with participants,
sessions, and rest/movie conditions so the whole batch + stats path can be exercised
offline. The generated data is NOT patient data and is safe to share.

Usage:
    python examples/generate_synthetic_data.py            # writes ./data/ demo cohort
    python examples/generate_synthetic_data.py --out data --minutes 3
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

XON_CHANNELS = ["F3", "F4", "C3", "C4", "Cz", "P3", "P4"]


# ---------------------------------------------------------------------------
# signal generation
# ---------------------------------------------------------------------------
def colored_noise(n: int, sfreq: float, exponent: float, rng: np.random.Generator,
                  knee_hz: float = 1.0) -> np.ndarray:
    """1/f^exponent noise (PSD slope = exponent) of length n, unit amplitude.

    A low-frequency knee (default 1 Hz) floors the spectrum below ``knee_hz`` so steep
    exponents don't blow up into unphysical drift - real scalp EEG has exactly such a
    knee. The 1-40 Hz fitting band sits above the knee, so the recovered exponent still
    matches the requested slope.
    """
    white = rng.standard_normal(n)
    fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / sfreq)
    scale = np.ones_like(freqs)
    nz = freqs > 0
    eff = np.maximum(freqs[nz], knee_hz)          # floor below the knee
    scale[nz] = eff ** (-exponent / 2.0)          # amplitude ~ f^(-exp/2) -> power ~ f^-exp
    fft = fft * scale
    sig = np.fft.irfft(fft, n=n)
    sig = sig / (np.std(sig) + 1e-12)
    return sig


def make_recording(sfreq: float, minutes: float, exponent: float, rng: np.random.Generator,
                   channels: Sequence[str] = XON_CHANNELS, alpha_hz: float = 10.0,
                   amp_uv: float = 12.0, bad_channel: Optional[str] = None,
                   burst_channel: Optional[str] = None) -> np.ndarray:
    """Return an (n_channels x n_samples) array in microvolts with a known exponent.

    Optionally inject one dead channel and/or one channel with amplitude bursts, so the
    bad-channel / high-offender logic has something to catch in a demo.
    """
    n = int(round(sfreq * minutes * 60.0))
    t = np.arange(n) / sfreq
    data = np.zeros((len(channels), n))
    for i, ch in enumerate(channels):
        sig = colored_noise(n, sfreq, exponent, rng)
        sig += 0.15 * np.sin(2 * np.pi * alpha_hz * t + rng.uniform(0, 2 * np.pi))  # small alpha bump
        data[i] = sig * amp_uv
    if bad_channel and bad_channel in channels:
        data[list(channels).index(bad_channel)] = rng.standard_normal(n) * 0.01  # near-flat/dead
    if burst_channel and burst_channel in channels:
        idx = list(channels).index(burst_channel)
        n_bursts = max(3, int(minutes * 8))
        for _ in range(n_bursts):
            start = rng.integers(0, max(1, n - int(sfreq)))
            width = int(sfreq * rng.uniform(0.1, 0.4))
            data[idx, start:start + width] += rng.uniform(150, 400) * np.sign(rng.standard_normal())
    return data


# ---------------------------------------------------------------------------
# minimal XDF writer  (enough for pyxdf.load_xdf to read it back)
# ---------------------------------------------------------------------------
def _varlen(n: int) -> bytes:
    if n < 2 ** 8:
        return struct.pack("<BB", 1, n)
    if n < 2 ** 32:
        return struct.pack("<BI", 4, n)
    return struct.pack("<BQ", 8, n)


def _chunk(tag: int, content: bytes) -> bytes:
    body = struct.pack("<H", tag) + content
    return _varlen(len(body)) + body


def _stream_header_xml(name: str, stype: str, ch_names: Sequence[str], sfreq: float) -> bytes:
    chans = "".join(f"<channel><label>{c}</label><unit>microvolts</unit>"
                    f"<type>EEG</type></channel>" for c in ch_names)
    xml = (f"<?xml version=\"1.0\"?><info><name>{name}</name><type>{stype}</type>"
           f"<channel_count>{len(ch_names)}</channel_count>"
           f"<nominal_srate>{sfreq}</nominal_srate><channel_format>float32</channel_format>"
           f"<created_at>0.0</created_at><desc><channels>{chans}</channels></desc></info>")
    return xml.encode("utf-8")


def _stream_footer_xml(n_samples: int, sfreq: float) -> bytes:
    xml = (f"<?xml version=\"1.0\"?><info><first_timestamp>0.0</first_timestamp>"
           f"<last_timestamp>{(n_samples - 1) / sfreq}</last_timestamp>"
           f"<sample_count>{n_samples}</sample_count></info>")
    return xml.encode("utf-8")


def write_xdf(path: str | Path, data_uv: np.ndarray, sfreq: float, ch_names: Sequence[str],
              stream_name: str = "Xon EEG", stream_type: str = "EEG", stream_id: int = 1) -> None:
    """Write (n_channels x n_samples) microvolt data as a valid float32 XDF file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n_ch, n_samp = data_uv.shape
    samples = data_uv.T.astype("<f4")           # samples x channels

    out = bytearray(b"XDF:")
    # FileHeader
    out += _chunk(1, b"<?xml version=\"1.0\"?><info><version>1.0</version></info>")
    # StreamHeader
    out += _chunk(2, struct.pack("<I", stream_id) + _stream_header_xml(stream_name, stream_type, ch_names, sfreq))
    # Samples chunk (tag 3): stream_id, num_samples varlen, then per-sample ts + values
    content = bytearray(struct.pack("<I", stream_id) + _varlen(n_samp))
    for i in range(n_samp):
        content += struct.pack("<B", 8)                     # timestamp present (8-byte double)
        content += struct.pack("<d", i / sfreq)
        content += samples[i].tobytes()                     # n_ch float32 values
    out += _chunk(3, bytes(content))
    # StreamFooter
    out += _chunk(6, struct.pack("<I", stream_id) + _stream_footer_xml(n_samp, sfreq))

    with open(path, "wb") as fh:
        fh.write(bytes(out))


# ---------------------------------------------------------------------------
# demo cohort
# ---------------------------------------------------------------------------
def generate_cohort(out_dir: str | Path, n_participants: int = 4, sessions: Sequence[str] = ("001", "002"),
                    conditions: Sequence[str] = ("rest", "movie"), minutes: float = 3.0,
                    sfreq: float = 250.0, seed: int = 0) -> List[Path]:
    """Write a demo cohort: each participant has a stable 'true' exponent (with a little
    session/condition noise). Movie recordings get a burst channel (noisier), a couple of
    recordings get a dead channel. Filenames follow P###_S###_<condition>.xdf."""
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    written: List[Path] = []
    for p in range(1, n_participants + 1):
        true_exp = float(rng.uniform(0.8, 1.8))             # this person's real exponent
        for ses in sessions:
            for cond in conditions:
                exp = true_exp + rng.normal(0, 0.05)        # small retest noise
                burst = "F3" if cond == "movie" else None   # movie = noisier
                dead = "P4" if (p == 2 and ses == sessions[0]) else None
                data = make_recording(sfreq, minutes, exp, rng, bad_channel=dead, burst_channel=burst)
                fname = f"P{p:03d}_S{ses}_{cond}.xdf"
                path = out_dir / fname
                write_xdf(path, data, sfreq, XON_CHANNELS, stream_name="Xon EEG", stream_type="EEG")
                written.append(path)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a synthetic Xon .xdf demo cohort.")
    ap.add_argument("--out", default="data", help="Output folder for the .xdf files.")
    ap.add_argument("--participants", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    files = generate_cohort(args.out, n_participants=args.participants, minutes=args.minutes, seed=args.seed)
    print(f"Wrote {len(files)} synthetic .xdf files to {args.out}/")
    for f in files:
        print("  ", f.name)
