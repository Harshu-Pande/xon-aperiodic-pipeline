"""Chop the continuous recording into fixed-length awake epochs."""
from __future__ import annotations

from typing import List, Tuple

import mne

from .logging_utils import step, info
from .preprocess import eeg_channel_names


def make_awake_epochs(raw: mne.io.BaseRaw, epoch_length_sec: float,
                      overlap_sec: float = 0.0) -> Tuple[mne.Epochs, List[str]]:
    """Fixed-length epochs over all good EEG channels (drops non-EEG and bads)."""
    step("STEP 3: Fixed-length awake epoching")
    good_eeg = eeg_channel_names(raw, exclude_bads=True)
    if not good_eeg:
        raise ValueError("No good EEG channels available for epoching.")
    raw_eeg = raw.copy().pick(good_eeg)

    overlap = float(overlap_sec) if overlap_sec else 0.0
    if overlap >= float(epoch_length_sec):
        overlap = 0.0     # guard: overlap must be < length

    epochs = mne.make_fixed_length_epochs(
        raw_eeg, duration=float(epoch_length_sec), overlap=overlap,
        preload=True, reject_by_annotation=True, verbose=False)

    info(f"  Analyzing channels ({len(good_eeg)}): {good_eeg}")
    info(f"  Epoch length: {epoch_length_sec:.2f} sec (overlap {overlap:.2f} sec)")
    info(f"  Total epochs before QC: {len(epochs)}")
    return epochs, good_eeg
