"""Preprocessing: channel typing, montage, cropping, filtering, bad-channel
detection, interpolation, ICA, and re-referencing.

Ported verbatim (behaviour-for-behaviour) from the validated monolith; only the
plumbing changed - functions take explicit parameters and log through the shared
logger instead of reading module globals or printing.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import mne
import numpy as np

from .logging_utils import step, info


def eeg_channel_names(raw: mne.io.BaseRaw, exclude_bads: bool = True) -> List[str]:
    """Names of the EEG channels (optionally excluding marked bads)."""
    picks = mne.pick_types(raw.info, eeg=True, exclude="bads" if exclude_bads else [])
    return [raw.ch_names[i] for i in picks]


def mark_obvious_non_eeg_channels(raw: mne.io.BaseRaw) -> mne.io.BaseRaw:
    """Relabel obvious non-EEG channels (ECG/EOG/EMG/accelerometer/BIP/trigger)."""
    type_map = {}
    for ch in raw.ch_names:
        cu = ch.upper()
        if "ECG" in cu or "EKG" in cu:
            type_map[ch] = "ecg"
        elif "EOG" in cu or "VEOG" in cu or "HEOG" in cu:
            type_map[ch] = "eog"
        elif "EMG" in cu:
            type_map[ch] = "emg"
        elif any(x in cu for x in ["ACC", "GYRO", "GSR", "EDA", "TEMP", "BAT", "IMP", "AUX", "BIP"]):
            type_map[ch] = "misc"     # BIP = Xon bipolar aux input, not scalp EEG
        elif any(x in cu for x in ["TRIG", "TRIGGER", "MARKER", "STATUS", "EVENT"]):
            type_map[ch] = "stim"
    if type_map:
        raw.set_channel_types(type_map, verbose=False)
        info(f"  Channel types corrected: {type_map}")
    return raw


def apply_montage(raw: mne.io.BaseRaw, montage_name: Optional[str]) -> mne.io.BaseRaw:
    """Attach 3D electrode positions from a standard montage. EEG-typed channels
    with no montage position (e.g. the Xon 'BIP' input) are reclassified to 'misc'
    so they drop out of every EEG step instead of poisoning the reference/PSD."""
    step("STEP 1c: Set electrode montage")
    if not montage_name:
        info("  montage=none; skipping. Spline interpolation will be unavailable.")
        return raw
    raw = raw.copy()
    try:
        montage = mne.channels.make_standard_montage(montage_name)
    except Exception as exc:
        info(f"  Could not build montage {montage_name!r} ({exc}); continuing without it.")
        return raw

    eeg_names = eeg_channel_names(raw, exclude_bads=False)
    montage_upper = {name.upper() for name in montage.ch_names}
    matched = [n for n in eeg_names if n.upper() in montage_upper]
    unmatched = [n for n in eeg_names if n.upper() not in montage_upper]
    try:
        raw.set_montage(montage, match_case=False, on_missing="warn", verbose=False)
    except Exception as exc:
        info(f"  set_montage failed ({exc}); continuing without positions.")
        return raw

    info(f"  Montage: {montage_name}")
    info(f"  EEG channels matched to positions ({len(matched)}): {matched}")
    if unmatched:
        raw.set_channel_types({name: "misc" for name in unmatched}, verbose=False)
        info(f"  EEG channels NOT in montage -> reclassified 'misc' and EXCLUDED "
             f"(no scalp position): {unmatched}")
    return raw


def resolve_channel(inst, channel: Optional[str] = None) -> str:
    """Pick a single analysis channel by name (or auto-pick the first EEG channel)."""
    names = list(inst.ch_names)
    if not names:
        raise ValueError("No channels found in the selected EEG stream.")
    if channel is None:
        if len(names) == 1:
            chosen = names[0]
        else:
            try:
                eeg = [n for n, t in zip(names, inst.get_channel_types()) if t == "eeg"]
            except Exception:
                eeg = []
            chosen = eeg[0] if eeg else names[0]
        info(f"  channel=None, using: {chosen}")
        return chosen
    upper = [n.upper() for n in names]
    if channel.upper() not in upper:
        raise ValueError(f"Channel {channel!r} not found. Available: {names}.")
    return names[upper.index(channel.upper())]


def crop_recording(raw: mne.io.BaseRaw, start_sec: Optional[float], stop_sec: Optional[float]) -> mne.io.BaseRaw:
    if start_sec is None and stop_sec is None:
        return raw
    step("STEP 1b: Crop recording")
    info(f"  Crop start: {start_sec}")
    info(f"  Crop stop : {stop_sec}")
    # Guard against a stop past the end of a short recording.
    tmax = None if stop_sec is None else min(float(stop_sec), float(raw.times[-1]))
    return raw.copy().crop(tmin=start_sec, tmax=tmax, include_tmax=False)


def apply_filter(raw: mne.io.BaseRaw, high_pass_hz: Optional[float], notch_freq_hz: Optional[float]) -> mne.io.BaseRaw:
    step("STEP 2: Filter")
    raw = raw.copy()
    if high_pass_hz is None and notch_freq_hz is None:
        info("  No filtering requested.")
        return raw
    if high_pass_hz is not None:
        info(f"  High-pass: {high_pass_hz} Hz")
        raw.filter(l_freq=high_pass_hz, h_freq=None, verbose=False)
    if notch_freq_hz is not None:
        nyquist = raw.info["sfreq"] / 2.0
        notch_freqs = np.arange(notch_freq_hz, nyquist, notch_freq_hz)
        if len(notch_freqs) > 0:
            info(f"  Notch frequencies: {list(np.round(notch_freqs, 2))} Hz")
            raw.notch_filter(freqs=notch_freqs, verbose=False)
        else:
            info("  Notch skipped because sampling rate is too low.")
    return raw


def detect_bad_channels(raw: mne.io.BaseRaw, zscore_thresh: float) -> mne.io.BaseRaw:
    """Flag dead/flat/railing EEG channels by robust variance z-score."""
    step("STEP 2b: Detect bad channels")
    raw = raw.copy()
    names = eeg_channel_names(raw, exclude_bads=False)
    if len(names) < 3:
        info(f"  Only {len(names)} EEG channel(s); skipping bad-channel detection.")
        return raw
    data = raw.get_data(picks=names)
    logvar = np.log(np.var(data, axis=1) + 1e-30)
    median = float(np.median(logvar))
    mad = float(np.median(np.abs(logvar - median)))
    if mad <= 0:
        info("  Channel variances are nearly identical; no bad channels flagged.")
        return raw
    robust_z = 0.6745 * (logvar - median) / mad
    bads = [n for n, z in zip(names, robust_z) if abs(z) > float(zscore_thresh)]
    # Stability guard for low channel counts: a variance z-score is only meaningful
    # when the "group" of channels is a stable reference. If the channels have nearly
    # identical variance (tiny MAD), a hair's difference explodes into a huge z-score
    # and the detector flags a MAJORITY of channels - which is nonsensical for a
    # bad-channel test (a real bad channel is the minority). In that case we trust none
    # and let epoch-level QC handle it. A genuine 1-2 outlier channel is still caught.
    max_flaggable = max(1, len(names) // 3)
    if len(bads) > max_flaggable:
        info(f"  Variance z-score flagged {len(bads)}/{len(names)} channels - too many to be "
             f"real bad channels (variances are near-identical); trusting none here.")
        bads = []
    if bads:
        raw.info["bads"] = sorted(set(list(raw.info["bads"]) + bads))
        for n, z in zip(names, robust_z):
            if n in bads:
                info(f"  Bad channel: {n} (robust variance z = {z:+.2f})")
        info(f"  Total bad channels: {len(bads)} -> excluded from ICA/reference/FOOOF")
    else:
        info("  No bad channels detected.")
    return raw


def detect_flat_railing_channels(raw: mne.io.BaseRaw, flat_thresh_uv: float, peak_thresh_uv: float,
                                 bad_percent: float = 20.0, min_duration: float = 0.1) -> mne.io.BaseRaw:
    """Flag flat/railing channels via MNE's annotate_amplitude. min_duration is kept
    at 0.1 s (not the 5 ms default) so oscillation zero-crossings don't false-flag
    healthy channels as flat."""
    names = eeg_channel_names(raw, exclude_bads=False)
    if len(names) < 1:
        return raw
    try:
        _, bads = mne.preprocessing.annotate_amplitude(
            raw, peak=peak_thresh_uv * 1e-6, flat=flat_thresh_uv * 1e-6,
            bad_percent=bad_percent, min_duration=min_duration, picks="eeg", verbose=False)
    except Exception as exc:
        info(f"  annotate_amplitude skipped ({exc}).")
        return raw
    new_bads = [b for b in bads if b not in raw.info["bads"]]
    if new_bads:
        raw = raw.copy()
        raw.info["bads"] = sorted(set(list(raw.info["bads"]) + new_bads))
        info(f"  annotate_amplitude flagged flat/railing channel(s): {new_bads}")
    else:
        info("  annotate_amplitude found no additional flat/railing channels.")
    return raw


def interpolate_bad_channels(raw: mne.io.BaseRaw, method: str = "average") -> Tuple[mne.io.BaseRaw, List[str]]:
    """Reconstruct all bad channels at once; return (raw, interpolated_names).

    method="average": each bad channel <- unweighted mean of the good channels
    (robust at 7 electrodes, where a spline's neighbour circle is unreliable).
    method="spline": MNE spherical-spline interpolate_bads() (needs positions).
    Interpolated channels are flagged and EXCLUDED from the AVERAGE downstream.
    """
    step(f"STEP 2b-i: Interpolate bad channels (method={method})")
    to_interpolate = list(raw.info["bads"])
    if not to_interpolate:
        info("  No bad channels to interpolate.")
        return raw, []

    good_eeg = eeg_channel_names(raw, exclude_bads=True)
    n_good = len(good_eeg)
    if n_good < 3:
        info(f"  Only {n_good} good EEG channel(s); refusing to interpolate "
             f"{len(to_interpolate)} bad channel(s). Leaving them excluded: {to_interpolate}")
        return raw, []

    if method == "average":
        raw = raw.copy()
        data = raw.get_data()
        good_idx = [raw.ch_names.index(g) for g in good_eeg]
        bad_idx = [raw.ch_names.index(b) for b in to_interpolate]
        good_mean = data[good_idx, :].mean(axis=0)
        for bi in bad_idx:
            raw._data[bi, :] = good_mean
        raw.info["bads"] = []
        info(f"  Interpolated {len(to_interpolate)} channel(s) with the average of "
             f"{n_good} good channels: {to_interpolate}")
        info("  NOTE: an averaged channel is a copy of the good-channel mean; it is "
             "flagged and EXCLUDED from the across-channel AVERAGE exponent.")
        return raw, to_interpolate

    # spline
    has_positions = True
    try:
        montage = raw.get_montage()
        has_positions = montage is not None and len(montage.get_positions().get("ch_pos", {})) > 0
    except Exception:
        has_positions = False
    if not has_positions:
        info("  No electrode positions (set a montage first); leaving bad channels excluded "
             f"instead of interpolating: {to_interpolate}")
        return raw, []
    try:
        raw = raw.copy().interpolate_bads(reset_bads=True, verbose=False)
    except Exception as exc:
        info(f"  interpolate_bads failed ({exc}); leaving bad channels excluded: {to_interpolate}")
        return raw, []
    info(f"  Interpolated {len(to_interpolate)} channel(s) with spherical splines: {to_interpolate}")
    info("  NOTE: interpolated channels are neighbour blends; flagged and excluded from the AVERAGE.")
    return raw, to_interpolate


def run_ica(raw: mne.io.BaseRaw, n_components: Optional[int], method: str, random_state: int,
            muscle_thresh: float, eog_thresh: float, ecg_thresh: float) -> mne.io.BaseRaw:
    """Fit ICA on good EEG channels and remove ocular/cardiac/muscle sources.
    Underpowered at 7 channels (a first pass at best), so a correlation fallback
    supplements the unstable low-N z-score detectors."""
    step("STEP 2c: ICA artifact removal")
    good_eeg = eeg_channel_names(raw, exclude_bads=True)
    n_eeg = len(good_eeg)
    if n_eeg < 2:
        info(f"  Only {n_eeg} good EEG channel(s); ICA needs >= 2. Skipping ICA.")
        return raw
    n_comp = min(int(n_components if n_components else n_eeg), n_eeg)
    try:
        ica = mne.preprocessing.ICA(n_components=n_comp, method=method, random_state=random_state,
                                    max_iter="auto", verbose=False)
        ica.fit(raw, picks="eeg", verbose=False)
    except Exception as exc:
        info(f"  ICA fit failed ({exc}); continuing without ICA.")
        return raw
    info(f"  ICA fit on {n_eeg} good EEG channels -> {ica.n_components_} components (method={method}).")

    exclude: set = set()
    ch_types = raw.get_channel_types()
    CORR_FALLBACK = 0.5

    def _corr_with_ref(ref_names: List[str]) -> List[int]:
        try:
            sources = ica.get_sources(raw).get_data()
            ref = raw.get_data(picks=ref_names)
            hits = []
            for comp in range(sources.shape[0]):
                for r in range(ref.shape[0]):
                    c = np.corrcoef(sources[comp], ref[r])[0, 1]
                    if np.isfinite(c) and abs(c) >= CORR_FALLBACK:
                        hits.append(comp)
                        break
            return hits
        except Exception:
            return []

    eog_names = [n for n, t in zip(raw.ch_names, ch_types) if t == "eog"]
    if eog_names:
        eog_idx: set = set()
        try:
            zidx, _ = ica.find_bads_eog(raw, threshold=eog_thresh, verbose=False)
            eog_idx |= set(zidx)
        except Exception as exc:
            info(f"  find_bads_eog skipped ({exc}).")
        eog_idx |= set(_corr_with_ref(eog_names))
        if eog_idx:
            info(f"  EOG-related components: {sorted(eog_idx)}")
        exclude |= eog_idx
    else:
        info("  No EOG channel; skipping ocular component auto-detection.")

    ecg_names = [n for n, t in zip(raw.ch_names, ch_types) if t == "ecg"]
    if ecg_names:
        ecg_idx: set = set()
        try:
            zidx, _ = ica.find_bads_ecg(raw, method="correlation", threshold=ecg_thresh, verbose=False)
            ecg_idx |= set(zidx)
        except Exception as exc:
            info(f"  find_bads_ecg skipped ({exc}).")
        ecg_idx |= set(_corr_with_ref(ecg_names))
        if ecg_idx:
            info(f"  ECG-related components: {sorted(ecg_idx)}")
        exclude |= ecg_idx
    else:
        info("  No ECG channel; skipping cardiac component auto-detection.")

    try:
        muscle_idx, _ = ica.find_bads_muscle(raw, threshold=muscle_thresh, verbose=False)
        if muscle_idx:
            info(f"  Muscle-related components: {muscle_idx}")
        exclude |= set(muscle_idx)
    except Exception as exc:
        info(f"  find_bads_muscle skipped ({exc}).")

    ica.exclude = sorted(exclude)
    if not ica.exclude:
        info("  No artifact components confidently identified; ICA leaves data unchanged.")
        return raw
    info(f"  Removing {len(ica.exclude)} component(s): {ica.exclude}")
    raw_clean = raw.copy()
    ica.apply(raw_clean, verbose=False)
    return raw_clean


def apply_reference(raw: mne.io.BaseRaw, reference, exclude_from_average=None) -> mne.io.BaseRaw:
    """Re-reference the EEG, or (reference=None) keep the device ear-clip (A2).

    ``exclude_from_average``: channels to leave OUT of the average-reference set.
    Interpolated channels belong here - an average-interpolated channel is literally
    the mean of the good channels, so including it in the average reference makes the
    reference equal to that channel and zeroes it out (which then reads as 'flat' and
    nukes every epoch). Excluding them makes the average reference well-defined.
    """
    step("STEP 2d: Re-reference")
    if reference is None:
        info("  Keeping the device's ear-clip (A2) reference; no re-referencing.")
        return raw
    good_eeg = eeg_channel_names(raw, exclude_bads=True)
    if len(good_eeg) < 2:
        info(f"  Only {len(good_eeg)} good EEG channel(s); skipping re-reference.")
        return raw
    if reference == "average":
        exclude_set = {c.upper() for c in (exclude_from_average or [])}
        ref_channels = [c for c in good_eeg if c.upper() not in exclude_set]
        if len(ref_channels) < 2:
            ref_channels = good_eeg
        if len(ref_channels) == len(good_eeg):
            raw = raw.copy().set_eeg_reference("average", projection=False, verbose=False)
            info(f"  Applied AVERAGE reference across {len(good_eeg)} good EEG channels.")
        else:
            raw = raw.copy().set_eeg_reference(ref_channels, projection=False, verbose=False)
            info(f"  Applied AVERAGE reference across {len(ref_channels)} real channels "
                 f"(excluded {len(good_eeg) - len(ref_channels)} interpolated from the reference set).")
        return raw
    ref_name = resolve_channel(raw, reference) if isinstance(reference, str) else reference
    if ref_name not in raw.ch_names:
        info(f"  Reference channel {reference!r} not found; keeping ear reference.")
        return raw
    raw = raw.copy().set_eeg_reference([ref_name], projection=False, verbose=False)
    info(f"  Re-referenced to single electrode: {ref_name}.")
    return raw
