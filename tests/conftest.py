"""Shared pytest fixtures. Everything runs on synthetic data - no real (HIPAA) files."""
import logging
import sys
from pathlib import Path

import numpy as np
import pytest

# make the package and the synthetic generator importable without installing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from generate_synthetic_data import make_recording, write_xdf, generate_cohort, XON_CHANNELS  # noqa: E402
from xon_aperiodic.config import load_config  # noqa: E402

logging.getLogger("xon_aperiodic").setLevel(logging.CRITICAL)


@pytest.fixture
def base_cfg(tmp_path):
    """A config with cropping/expected-duration disabled (synthetic files are short)."""
    cfg = load_config()
    cfg.data["crop"]["start_sec"] = None
    cfg.data["crop"]["stop_sec"] = None
    cfg.data["crop"]["expected_duration_min"] = None
    cfg.data["io"]["output_dir"] = str(tmp_path / "outputs")
    return cfg


@pytest.fixture
def clean_xdf(tmp_path):
    """A single clean synthetic recording with a known exponent of 1.2."""
    rng = np.random.default_rng(0)
    # amp 8 uV -> comfortable headroom under the 100 uV artifact threshold (clean resting EEG)
    data = make_recording(250.0, 2.0, 1.2, rng, amp_uv=8.0)
    path = tmp_path / "P001_S001_rest.xdf"
    write_xdf(path, data, 250.0, XON_CHANNELS)
    return path


@pytest.fixture
def cohort_dir(tmp_path):
    """A small demo cohort (2 participants x 2 sessions x 2 conditions)."""
    data_dir = tmp_path / "data"
    generate_cohort(data_dir, n_participants=2, minutes=1.5, seed=1)
    return data_dir
