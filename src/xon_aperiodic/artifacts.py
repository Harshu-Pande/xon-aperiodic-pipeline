"""Epoch-level artifact rejection with per-channel attribution.

Four mechanisms, in order: amplitude/flat (peak-to-peak), gradient (sample-to-sample
slope, reproducing Krigolson's routine behind the Xon papers), variance z-score, and
muscle z-score (excess high-frequency power). For every dropped epoch we also record
WHICH channel(s) triggered it - the attribution that distinguishes "one bad electrode
poisoning whole epochs" from "the whole cap is noisy".

Behaviour is identical to the validated monolith; only globals -> parameters.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import mne
import numpy as np
import pandas as pd

from .logging_utils import step, info


def column_zscores(values: np.ndarray) -> np.ndarray:
    """Per-column z-scores; columns with zero variance become 0 (not NaN)."""
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    std_safe = np.where(std > 0, std, 1.0)
    z = (values - mean) / std_safe
    z[:, std == 0] = 0.0
    return z


def reject_artifacts(
    epochs: mne.Epochs,
    amplitude_thresh_uv: float,
    flat_thresh_uv: float,
    variance_zscore_thresh: Optional[float],
    muscle_zscore_thresh: Optional[float],
    muscle_hf_hz: float,
    gradient_thresh_uv_per_ms: Optional[float] = None,
    ignore_channels: Optional[Sequence[str]] = None,
) -> Tuple[mne.Epochs, pd.DataFrame, dict]:
    """Return (clean_epochs, per-epoch QC dataframe, qc_stats dict).

    ``ignore_channels`` (e.g. average-interpolated channels) still get per-channel
    attribution counts, but they do NOT drive the epoch DROP decision. Rationale: a
    reconstructed channel is not an independent measurement, and an average-interpolated
    channel that becomes ~0 after average referencing would otherwise read as 'flat' and
    reject every epoch. QC should be driven by real measured channels.
    """
    step("STEP 4: Artifact rejection")
    n_before = len(epochs)
    if n_before == 0:
        raise RuntimeError("No epochs were created. Check recording length and epoch.length_sec.")

    all_onsets_sec = epochs.events[:, 0] / epochs.info["sfreq"]
    info(f"  Amplitude reject: > {amplitude_thresh_uv:.1f} uV peak-to-peak")
    info(f"  Flat reject: < {flat_thresh_uv:.1f} uV peak-to-peak")
    if gradient_thresh_uv_per_ms is not None:
        info(f"  Gradient reject: > {gradient_thresh_uv_per_ms:.1f} uV/ms (sample-to-sample slope)")
    if variance_zscore_thresh is not None:
        info(f"  Variance z reject: > {variance_zscore_thresh:.1f}")
    if muscle_zscore_thresh is not None:
        info(f"  Muscle z reject: > {muscle_zscore_thresh:.1f}, using > {muscle_hf_hz:.1f} Hz")

    epochs = epochs.copy()
    ch_names = list(epochs.ch_names)
    ignore_set = {str(c).upper() for c in (ignore_channels or [])}
    consider = np.array([ch.upper() not in ignore_set for ch in ch_names])  # channels that drive drops
    if not consider.any():
        consider = np.ones(len(ch_names), dtype=bool)
    if ignore_set:
        info(f"  Channels excluded from the epoch-drop decision (reconstructed): "
             f"{[c for c in ch_names if c.upper() in ignore_set]}")
    hits_amp_flat = {ch: 0 for ch in ch_names}
    hits_gradient = {ch: 0 for ch in ch_names}
    hits_variance = {ch: 0 for ch in ch_names}
    hits_muscle = {ch: 0 for ch in ch_names}

    # Amplitude / flat, per channel (recompute peak-to-peak the way MNE's reject/flat does).
    pre_data = epochs.get_data()                       # epochs x channels x time, Volts
    ptp = pre_data.max(axis=2) - pre_data.min(axis=2)  # epochs x channels
    af_hit = (ptp > amplitude_thresh_uv * 1e-6) | (ptp < flat_thresh_uv * 1e-6)
    for j, ch in enumerate(ch_names):
        hits_amp_flat[ch] = int(af_hit[:, j].sum())
    # Drop an epoch if ANY considered (real) channel exceeds. Manual drop so we can
    # exclude reconstructed channels from the decision.
    af_drop = [i for i in range(n_before) if af_hit[i, consider].any()]
    if af_drop:
        epochs.drop(af_drop, reason="AMPLITUDE/FLAT", verbose=False)
    n_after_fixed = len(epochs)
    n_after_amp_flat = n_after_fixed
    n_gradient_dropped = n_variance_flagged = n_muscle_flagged = 0
    info(f"  After amplitude/flat QC: {n_after_fixed}/{n_before} epochs remain")

    # Manual GRADIENT rejection: |diff| in uV / sample-spacing in ms = uV/ms.
    # (Reproduces Krigolson's 'Gradient' routine: a 40 uV/sample step at 250 Hz == 10 uV/ms.)
    if gradient_thresh_uv_per_ms is not None and n_after_fixed > 0:
        data = epochs.get_data()
        dt_ms = 1000.0 / epochs.info["sfreq"]
        grad_uv_per_ms = np.abs(np.diff(data, axis=2)) * 1e6 / dt_ms
        grad_per_ch = grad_uv_per_ms.max(axis=2)       # epochs x channels
        grad_hit = grad_per_ch > float(gradient_thresh_uv_per_ms)
        for j, ch in enumerate(ch_names):
            hits_gradient[ch] = int(grad_hit[:, j].sum())
        grad_drop = [i for i in range(grad_hit.shape[0]) if grad_hit[i, consider].any()]
        if grad_drop:
            epochs.drop(grad_drop, reason="GRADIENT", verbose=False)
        n_gradient_dropped = len(grad_drop)
        info(f"  Gradient outliers rejected: {n_gradient_dropped}")
        n_after_fixed = len(epochs)

    do_variance = variance_zscore_thresh is not None
    do_muscle = muscle_zscore_thresh is not None
    min_epochs_for_z = 5

    if (do_variance or do_muscle) and n_after_fixed >= min_epochs_for_z:
        data = epochs.get_data()
        flag_variance = np.zeros(n_after_fixed, dtype=bool)
        flag_muscle = np.zeros(n_after_fixed, dtype=bool)

        if do_variance:
            var_z = column_zscores(data.var(axis=2))
            var_hit = var_z > float(variance_zscore_thresh)
            flag_variance = var_hit[:, consider].any(axis=1)
            for j, ch in enumerate(ch_names):
                hits_variance[ch] = int(var_hit[:, j].sum())

        if do_muscle:
            sfreq = epochs.info["sfreq"]
            if muscle_hf_hz < sfreq / 2.0:
                hf = epochs.copy().filter(l_freq=muscle_hf_hz, h_freq=None, verbose=False)
                muscle_z = column_zscores(hf.get_data().var(axis=2))
                mus_hit = muscle_z > float(muscle_zscore_thresh)
                flag_muscle = mus_hit[:, consider].any(axis=1)
                for j, ch in enumerate(ch_names):
                    hits_muscle[ch] = int(mus_hit[:, j].sum())
            else:
                info("  Muscle QC skipped because muscle_hf_hz is above Nyquist.")

        drop_indices, drop_reasons = [], []
        for idx in range(n_after_fixed):
            reasons = []
            if flag_variance[idx]:
                reasons.append("VARIANCE")
            if flag_muscle[idx]:
                reasons.append("MUSCLE")
            if reasons:
                drop_indices.append(idx)
                drop_reasons.append("+".join(reasons))
        if drop_indices:
            epochs.drop(drop_indices, reason=drop_reasons, verbose=False)
        n_variance_flagged = int(flag_variance.sum())
        n_muscle_flagged = int(flag_muscle.sum())
        info(f"  Variance outliers rejected: {n_variance_flagged}")
        info(f"  Muscle outliers rejected: {n_muscle_flagged}")
    elif do_variance or do_muscle:
        info(f"  Adaptive z-score QC skipped because only {n_after_fixed} epochs remain.")

    n_after = len(epochs)
    pct_kept = 100.0 * n_after / n_before if n_before else 0.0
    info(f"  Final clean epochs: {n_after}/{n_before} ({pct_kept:.1f}% kept)")

    qc_stats = dict(
        epochs_before_qc=int(n_before),
        epochs_after_amp_flat=int(n_after_amp_flat),
        epochs_dropped_amp_flat=int(n_before - n_after_amp_flat),
        epochs_dropped_gradient=int(n_gradient_dropped),
        epochs_flagged_variance=int(n_variance_flagged),
        epochs_flagged_muscle=int(n_muscle_flagged),
        epochs_final_clean=int(n_after),
        pct_epochs_rejected=round(100.0 - pct_kept, 2),
        pct_epochs_kept=round(pct_kept, 2),
    )
    qc_stats["per_channel_hits"] = {
        ch: dict(amp_flat=hits_amp_flat.get(ch, 0), gradient=hits_gradient.get(ch, 0),
                 variance=hits_variance.get(ch, 0), muscle=hits_muscle.get(ch, 0))
        for ch in ch_names
    }

    if n_after == 0:
        raise RuntimeError(
            "All epochs were rejected. Common fixes:\n"
            "  1. Confirm xdf.data_units is correct (set 'V' if values are already volts).\n"
            "  2. Raise artifacts.amplitude_threshold_uv (e.g. 300 or 500).\n"
            "  3. Temporarily set variance/muscle_zscore_threshold to null.")

    qc_rows = []
    for i, reasons in enumerate(epochs.drop_log):
        kept = len(reasons) == 0
        qc_rows.append(dict(
            epoch_index=i,
            onset_sec=round(float(all_onsets_sec[i]), 3) if i < len(all_onsets_sec) else None,
            kept=kept,
            rejection_reason=", ".join(reasons) if not kept else "",
        ))
    return epochs, pd.DataFrame(qc_rows), qc_stats
