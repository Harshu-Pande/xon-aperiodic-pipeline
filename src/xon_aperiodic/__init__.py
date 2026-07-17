"""Xon Aperiodic Pipeline.

Turn Xon headset .xdf EEG recordings into the aperiodic (1/f) exponent - the
excitation/inhibition marker used in this Alzheimer's research - with transparent
artifact rejection, granular QC, publication-quality figures, and statistics.

Public entry points:
    from xon_aperiodic import load_config, run_pipeline, run_batch
"""
from __future__ import annotations

from .config import Config, load_config
from .pipeline import run_pipeline
from .batch import run_batch

__version__ = "1.0.0"
__all__ = ["Config", "load_config", "run_pipeline", "run_batch", "__version__"]
