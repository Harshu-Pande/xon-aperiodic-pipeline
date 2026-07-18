"""Spectrum and aperiodic fitting: Welch PSD -> FOOOF/specparam -> exponent.

Also the CONVERGENCE analysis: how the exponent estimate stabilises as clean data
accumulates - the direct test of the study's core question, "how few minutes of a
noisy recording are enough to recover a reliable exponent?"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import mne
import numpy as np
import pandas as pd

from .logging_utils import step, info

try:
    from fooof import FOOOF
except ImportError:                       # pragma: no cover
    try:
        from specparam import SpectralModel as FOOOF
    except ImportError as exc:
        raise ImportError("Needs FOOOF or specparam: pip install fooof") from exc


def compute_psd(epochs: mne.Epochs, epoch_length_sec: float, verbose: bool = True
                ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Average Welch PSD for every channel. Returns (freqs, psd[ch x freq], ch_names)."""
    if verbose:
        step("STEP 5: Compute average PSD with Welch")
    sfreq = epochs.info["sfreq"]
    n_samples = int(round(epoch_length_sec * sfreq))
    n_fft = min(int(round(4.0 * sfreq)), n_samples)
    n_overlap = n_fft // 2 if n_fft < n_samples else 0
    fmax = min(100.0, sfreq / 2.0 - 1.0)
    if fmax <= 1.0:
        raise ValueError("Sampling rate is too low to compute PSD above 1 Hz.")
    if verbose:
        info(f"  Clean epochs used: {len(epochs)}")
        info(f"  Channels: {len(epochs.ch_names)}")
        info(f"  Welch window: {n_fft / sfreq:.2f} sec")
        info(f"  Frequency resolution: {sfreq / n_fft:.3f} Hz")

    spectrum = epochs.compute_psd(method="welch", fmin=1.0, fmax=fmax, n_fft=n_fft,
                                  n_overlap=n_overlap, verbose=False)
    avg = spectrum.average()
    freqs = np.asarray(avg.freqs)
    psd_2d = np.atleast_2d(avg.get_data())
    ch_names = list(avg.ch_names)
    good = np.isfinite(freqs) & (freqs > 0)
    freqs, psd_2d = freqs[good], psd_2d[:, good]
    if len(freqs) == 0:
        raise RuntimeError("PSD has no valid frequency values.")
    if verbose:
        info(f"  PSD frequency range: {freqs[0]:.2f}-{freqs[-1]:.2f} Hz")
    return freqs, psd_2d, ch_names


def fit_fooof(freqs: np.ndarray, psd: np.ndarray, freq_range: Sequence[float],
              fooof_settings: Dict[str, Any], verbose: bool = True, label: str = ""
              ) -> Tuple[Any, Dict[str, Any]]:
    """Fit one PSD and return (model, metrics dict)."""
    if verbose:
        step("STEP 6: Fit FOOOF")
    frange = [float(freq_range[0]), float(freq_range[1])]
    if frange[1] > float(np.max(freqs)):
        old = frange[1]; frange[1] = float(np.max(freqs))
        if verbose:
            info(f"  Upper FOOOF range capped from {old:.1f} to {frange[1]:.1f} Hz.")
    if frange[0] < float(np.min(freqs)):
        old = frange[0]; frange[0] = float(np.min(freqs))
        if verbose:
            info(f"  Lower FOOOF range raised from {old:.1f} to {frange[0]:.1f} Hz.")
    if frange[1] <= frange[0]:
        raise ValueError(f"Invalid FOOOF range after adjustment: {frange}")

    fm = FOOOF(**fooof_settings, verbose=False)
    fm.fit(freqs, psd, frange)
    exponent = fm.get_params("aperiodic_params", "exponent")
    offset = fm.get_params("aperiodic_params", "offset")
    r_squared = fm.get_params("r_squared")
    error = fm.get_params("error")
    n_peaks = len(fm.peak_params_) if fm.peak_params_ is not None else 0
    if verbose:
        tag = f" [{label}]" if label else ""
        info(f"  FOOOF range: {frange[0]:.1f}-{frange[1]:.1f} Hz")
        info(f"  Aperiodic exponent{tag}: {exponent:.4f}")
        info(f"  Aperiodic offset:   {offset:.4f}")
        info(f"  R-squared:          {r_squared:.4f}")
        info(f"  Fit error:          {error:.4f}")
        info(f"  Peaks detected:     {n_peaks}")
    return fm, dict(
        aperiodic_exponent=round(float(exponent), 6),
        aperiodic_offset=round(float(offset), 6),
        r_squared=round(float(r_squared), 6),
        fit_error=round(float(error), 6),
        n_peaks_detected=int(n_peaks),
        fooof_freq_low_hz=frange[0],
        fooof_freq_high_hz=frange[1],
    )


def extract_peak_table(fm: Any, subject_id: str, channel: str, segment_label: str) -> pd.DataFrame:
    cols = ["subject_id", "channel", "segment", "peak_index",
            "center_frequency_hz", "peak_power", "bandwidth_hz"]
    if fm.peak_params_ is None or len(fm.peak_params_) == 0:
        return pd.DataFrame(columns=cols)
    rows = []
    for i, (cf, pw, bw) in enumerate(fm.peak_params_, start=1):
        rows.append(dict(subject_id=subject_id, channel=channel, segment=segment_label,
                         peak_index=i, center_frequency_hz=round(float(cf), 6),
                         peak_power=round(float(pw), 6), bandwidth_hz=round(float(bw), 6)))
    return pd.DataFrame(rows, columns=cols)


def fit_segment(epochs: mne.Epochs, subject_id: str, segment_label: str, start_min: float,
                end_min: float, epoch_length_sec: float, fooof_freq_range: Sequence[float],
                fooof_settings: Dict[str, Any], verbose: bool = True,
                interpolated_channels: Sequence[str] = ()
                ) -> Tuple[List[Dict[str, Any]], pd.DataFrame, np.ndarray, np.ndarray, Dict[str, Any], List[str]]:
    """FOOOF every channel plus an across-channel AVERAGE row (interpolated channels
    are fit and reported but EXCLUDED from the AVERAGE)."""
    interp_set = {str(c).upper() for c in interpolated_channels}
    freqs, psd_2d, ch_names = compute_psd(epochs, epoch_length_sec, verbose=verbose)
    clean_minutes = round(len(epochs) * epoch_length_sec / 60.0, 4)
    if verbose:
        step("STEP 6: Fit FOOOF per channel")

    rows: List[Dict[str, Any]] = []
    peak_frames: List[pd.DataFrame] = []
    fm_by_channel: Dict[str, Any] = {}
    exps, offs, r2s = [], [], []

    for ci, channel in enumerate(ch_names):
        psd = psd_2d[ci]
        mask = np.isfinite(psd) & (psd > 0)
        is_interp = channel.upper() in interp_set
        base = dict(subject_id=subject_id, channel=channel, segment=segment_label,
                    segment_start_min=start_min, segment_end_min=end_min,
                    clean_epochs=len(epochs), clean_minutes=clean_minutes, interpolated=is_interp)
        if mask.sum() < 5:
            base["error"] = "Too few valid PSD points for FOOOF."
            rows.append(base); continue
        try:
            fm, metrics = fit_fooof(freqs[mask], psd[mask], fooof_freq_range, fooof_settings,
                                    verbose=verbose, label=channel)
        except Exception as exc:
            base["error"] = str(exc); rows.append(base); continue
        base.update(metrics)
        rows.append(base)
        peak_frames.append(extract_peak_table(fm, subject_id, channel, segment_label))
        fm_by_channel[channel] = fm
        if not is_interp:
            exps.append(metrics["aperiodic_exponent"])
            offs.append(metrics["aperiodic_offset"])
            r2s.append(metrics["r_squared"])

    if exps:
        avg_row = dict(subject_id=subject_id, channel="AVERAGE", segment=segment_label,
                       segment_start_min=start_min, segment_end_min=end_min,
                       clean_epochs=len(epochs), clean_minutes=clean_minutes,
                       aperiodic_exponent=round(float(np.mean(exps)), 6),
                       aperiodic_offset=round(float(np.mean(offs)), 6),
                       r_squared=round(float(np.mean(r2s)), 6),
                       aperiodic_exponent_sd=round(float(np.std(exps)), 6),
                       n_channels_averaged=len(exps), interpolated=False,
                       n_interpolated_excluded=int(sum(1 for c in ch_names if c.upper() in interp_set)))
        rows.append(avg_row)
        if verbose:
            n_excl = avg_row["n_interpolated_excluded"]
            excl_note = f", excluding {n_excl} interpolated" if n_excl else ""
            info(f"\n  Across-channel average exponent: {avg_row['aperiodic_exponent']:.4f} "
                 f"(+/- {avg_row['aperiodic_exponent_sd']:.4f} over {len(exps)} channels{excl_note})")

    peak_df = pd.concat(peak_frames, ignore_index=True) if peak_frames else pd.DataFrame()
    return rows, peak_df, freqs, psd_2d, fm_by_channel, ch_names


def _avg_psd_exponent(epochs_subset: mne.Epochs, epoch_length_sec: float,
                      fooof_freq_range: Sequence[float], fooof_settings: Dict[str, Any],
                      keep_idx: Sequence[int]) -> Tuple[float, float]:
    """Fit the exponent on the channel-averaged PSD of an epoch subset. Returns
    (exponent, r_squared) or (nan, nan). Averaging the PSD across channels first is a
    standard, fast estimator and keeps the reliability analysis internally consistent."""
    if len(epochs_subset) < 3:
        return float("nan"), float("nan")
    try:
        freqs, psd_2d, _ = compute_psd(epochs_subset, epoch_length_sec, verbose=False)
    except Exception:
        return float("nan"), float("nan")
    idx = [i for i in keep_idx if i < psd_2d.shape[0]] or list(range(psd_2d.shape[0]))
    psd = np.nanmean(psd_2d[idx, :], axis=0)
    mask = np.isfinite(psd) & (psd > 0)
    if mask.sum() < 5:
        return float("nan"), float("nan")
    try:
        _, metrics = fit_fooof(freqs[mask], psd[mask], fooof_freq_range, fooof_settings, verbose=False)
        return float(metrics["aperiodic_exponent"]), float(metrics["r_squared"])
    except Exception:
        return float("nan"), float("nan")


def _fit_mean_psd(freqs: np.ndarray, psd_mean: np.ndarray, fooof_freq_range: Sequence[float],
                  fooof_settings: Dict[str, Any]) -> Tuple[float, float]:
    mask = np.isfinite(psd_mean) & (psd_mean > 0)
    if mask.sum() < 5:
        return float("nan"), float("nan")
    try:
        _, metrics = fit_fooof(freqs[mask], psd_mean[mask], fooof_freq_range, fooof_settings, verbose=False)
        return float(metrics["aperiodic_exponent"]), float(metrics["r_squared"])
    except Exception:
        return float("nan"), float("nan")


def compute_duration_curve(epochs: mne.Epochs, epoch_length_sec: float,
                           fooof_freq_range: Sequence[float], fooof_settings: Dict[str, Any],
                           step_sec: float = 30.0, interpolated_channels: Sequence[str] = (),
                           max_points: int = 20) -> pd.DataFrame:
    """How the exponent estimate behaves as clean data accumulates - the raw material
    for the reliability-vs-duration analysis.

    For each cumulative duration (first k clean epochs) we fit the channel-averaged
    exponent three ways: all / odd / even epochs within the first k. The odd/even split
    powers split-half reliability; ``exponent_all`` across sessions powers test-retest.

    FAST: the per-epoch Welch PSD is computed ONCE, then each cumulative estimate is just
    a mean over the first-k per-epoch spectra (+ one FOOOF fit) - instead of re-running
    Welch at every duration, which is what made this step slow on long recordings.
    """
    interp_set = {str(c).upper() for c in interpolated_channels}
    n_total = len(epochs)
    if n_total < 6:
        return pd.DataFrame()

    ch_names = list(epochs.ch_names)
    keep_idx = [i for i, c in enumerate(ch_names) if c.upper() not in interp_set] or list(range(len(ch_names)))

    # per-epoch PSD, computed once
    sfreq = epochs.info["sfreq"]
    n_samples = int(round(epoch_length_sec * sfreq))
    n_fft = min(int(round(4.0 * sfreq)), n_samples)
    n_overlap = n_fft // 2 if n_fft < n_samples else 0
    fmax = min(100.0, sfreq / 2.0 - 1.0)
    try:
        spec = epochs.compute_psd(method="welch", fmin=1.0, fmax=fmax, n_fft=n_fft,
                                  n_overlap=n_overlap, verbose=False)
        freqs = np.asarray(spec.freqs)
        per_epoch = np.asarray(spec.get_data())          # epochs x channels x freqs
    except Exception:
        return pd.DataFrame()
    good = np.isfinite(freqs) & (freqs > 0)
    freqs = freqs[good]
    per_epoch = per_epoch[:, :, good]
    # channel-averaged per-epoch spectrum over the kept channels
    ch_avg = per_epoch[:, keep_idx, :].mean(axis=1)      # epochs x freqs

    step_epochs = max(1, int(round(step_sec / epoch_length_sec)))
    ks = list(range(2 * step_epochs, n_total + 1, step_epochs))
    if not ks or ks[-1] != n_total:
        ks.append(n_total)
    if len(ks) > max_points:                              # cap for a clean, bounded curve
        idx = np.linspace(0, len(ks) - 1, max_points).round().astype(int)
        ks = sorted(set(ks[i] for i in idx))

    rows = []
    for k in ks:
        odd_i = list(range(0, k, 2))
        even_i = list(range(1, k, 2))
        exp_all, r2_all = _fit_mean_psd(freqs, ch_avg[:k].mean(axis=0), fooof_freq_range, fooof_settings)
        exp_odd, _ = _fit_mean_psd(freqs, ch_avg[odd_i].mean(axis=0), fooof_freq_range, fooof_settings)
        exp_even, _ = _fit_mean_psd(freqs, ch_avg[even_i].mean(axis=0), fooof_freq_range, fooof_settings)
        rows.append(dict(clean_minutes=round(k * epoch_length_sec / 60.0, 4), clean_epochs=k,
                         exponent_all=round(exp_all, 6), exponent_odd=round(exp_odd, 6),
                         exponent_even=round(exp_even, 6), r2_all=round(r2_all, 6)))
    return pd.DataFrame(rows)
