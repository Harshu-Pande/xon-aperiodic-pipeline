"""Configuration: load the single config.yaml into a typed, validated object.

Every setting the pipeline uses lives in ``config/config.yaml`` and is loaded here
into a :class:`Config` dataclass. Nothing in the codebase reads a global constant;
functions receive ``cfg`` (or the specific values they need) explicitly. That is
what makes the pipeline portable and easy to reason about: one file to edit, one
object threaded through the code.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ---------------------------------------------------------------------------
# Defaults live here as well as in config.yaml, so the pipeline still runs with
# a partial (or missing) config file - any key you omit falls back to these.
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    "io": {
        "input_dir": "data",
        "recursive": True,
        "file_glob": "*",          # Xon exports often have no .xdf extension; non-data files are skipped
        "output_dir": "outputs",
    },
    "metadata": {
        "patterns": {
            "participant": r"P0*([0-9]+)",
            "session": r"S0*([0-9]+)",
            "condition": r"(rest|movie|film|video)",
        },
        "participant_prefix": "P",
        "participant_zero_pad": 3,
        "condition_aliases": {"rest": "rest", "movie": "movie", "film": "movie", "video": "movie"},
        "manifest": None,
    },
    "xdf": {"stream_name": None, "stream_type": None, "data_units": "uV"},
    "crop": {"start_sec": 60, "stop_sec": 1860, "expected_duration_min": 30.0},
    "filter": {"high_pass_hz": 0.1, "notch_freq_hz": 60.0},
    "montage": {"name": "standard_1020"},
    "epoch": {"length_sec": 1.0, "overlap_sec": 0.1},
    "artifacts": {
        "amplitude_threshold_uv": 100.0,
        "gradient_threshold_uv_per_ms": 10.0,
        "flat_threshold_uv": 1.0,
        "variance_zscore_threshold": 3.0,
        "muscle_zscore_threshold": 3.0,
        "muscle_hf_hz": 30.0,
        "detect_bad_channels": True,
        "bad_channel_zscore": 3.0,
        "use_annotate_amplitude": True,
        "interpolate_bad_channels": True,
        "interpolation_method": "average",
        "run_ica": False,
        "ica_n_components": None,
        "ica_method": "infomax",
        "ica_random_state": 97,
        "ica_muscle_threshold": 0.8,
        "ica_eog_threshold": 3.0,
        "ica_ecg_threshold": 0.3,
        "reference": None,
    },
    "exponent_rejection": {"enabled": True, "threshold": 0.5},
    "high_offender": {
        "enabled": False,
        "share_threshold": 50.0,
        "min_reject_pct": 15.0,
        "action": "interpolate",
    },
    "fooof": {
        "freq_range": [1, 40],
        "aperiodic_mode": "fixed",
        "peak_width_limits": [1.0, 12.0],
        "max_n_peaks": 6,
        "min_peak_height": 0.0,
        "peak_threshold": 2.0,
    },
    "analysis": {
        "block_analysis": True,
        "block_length_min": 5.0,
        "reliability_analysis": True,
        "reliability_step_sec": 30.0,
    },
    "performance": {
        "n_jobs": "auto",       # "auto" = pick a safe number of parallel workers; or an integer
        "max_workers": 6,       # never use more than this many parallel workers (RAM safety)
    },
    "stats": {
        "enabled": True,
        "regions": {"frontal": ["F3", "F4"], "central": ["C3", "C4", "Cz"], "parietal": ["P3", "P4"]},
        "quiet_condition": "rest",
        "noisy_condition": "movie",
        "reliability_split_half_target": 0.90,
        "reliability_icc_target": 0.75,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` onto a copy of ``base`` (override wins)."""
    out = copy.deepcopy(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


@dataclass
class Config:
    """Typed view over the merged configuration.

    Sub-sections are kept as plain dicts (``io``, ``artifacts`` ...) so new keys in
    config.yaml never break loading, while convenience accessors expose the values
    the pipeline uses most. Access anything with ``cfg.get("artifacts", "amplitude_threshold_uv")``.
    """

    data: Dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    config_path: Optional[str] = None
    project_root: Optional[str] = None

    # -- construction --------------------------------------------------------
    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]], config_path: Optional[str] = None,
                  project_root: Optional[str] = None) -> "Config":
        merged = _deep_merge(DEFAULTS, raw or {})
        cfg = cls(data=merged, config_path=config_path, project_root=project_root)
        cfg.validate()
        return cfg

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh) or {}
        # project_root = the folder that contains config/ (so relative io paths
        # resolve the same no matter which directory you launch from).
        root = path.parent.parent if path.parent.name == "config" else path.parent
        return cls.from_dict(raw, config_path=str(path), project_root=str(root))

    # -- access helpers ------------------------------------------------------
    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.data.get(section, {}).get(key, default)

    def section(self, name: str) -> Dict[str, Any]:
        return self.data.get(name, {})

    def resolve_path(self, path_str: str) -> Path:
        """Resolve a possibly-relative path against the project root."""
        p = Path(path_str).expanduser()
        if p.is_absolute():
            return p
        base = Path(self.project_root) if self.project_root else Path.cwd()
        return (base / p).resolve()

    @property
    def input_dir(self) -> Path:
        return self.resolve_path(self.get("io", "input_dir", "data"))

    @property
    def output_dir(self) -> Path:
        return self.resolve_path(self.get("io", "output_dir", "outputs"))

    @property
    def fooof_settings(self) -> Dict[str, Any]:
        f = self.section("fooof")
        return dict(
            peak_width_limits=tuple(f.get("peak_width_limits", [1.0, 12.0])),
            max_n_peaks=int(f.get("max_n_peaks", 6)),
            min_peak_height=float(f.get("min_peak_height", 0.0)),
            peak_threshold=float(f.get("peak_threshold", 2.0)),
            aperiodic_mode=str(f.get("aperiodic_mode", "fixed")),
        )

    @property
    def reference(self) -> Optional[str]:
        """Normalise the reference setting ('ear'/'none'/'' -> None)."""
        ref = self.get("artifacts", "reference", None)
        if ref is None:
            return None
        if isinstance(ref, str) and ref.strip().lower() in {"ear", "none", ""}:
            return None
        return ref

    @property
    def montage_name(self) -> Optional[str]:
        m = self.get("montage", "name", None)
        if m is None or str(m).strip().lower() in {"none", ""}:
            return None
        return str(m)

    # -- validation ----------------------------------------------------------
    def validate(self) -> None:
        a = self.section("artifacts")
        if str(a.get("interpolation_method")) not in {"average", "spline"}:
            raise ValueError("artifacts.interpolation_method must be 'average' or 'spline'.")
        if str(a.get("ica_method")) not in {"fastica", "infomax", "picard"}:
            raise ValueError("artifacts.ica_method must be fastica/infomax/picard.")
        if str(self.get("high_offender", "action")) not in {"interpolate", "exclude"}:
            raise ValueError("high_offender.action must be 'interpolate' or 'exclude'.")
        if str(self.get("xdf", "data_units")) not in {"uV", "mV", "V"}:
            raise ValueError("xdf.data_units must be 'uV', 'mV', or 'V'.")
        fr = self.get("fooof", "freq_range", [1, 40])
        if not (isinstance(fr, (list, tuple)) and len(fr) == 2 and fr[0] < fr[1]):
            raise ValueError("fooof.freq_range must be [low, high] with low < high.")
        if float(self.get("epoch", "overlap_sec", 0.0)) >= float(self.get("epoch", "length_sec", 1.0)):
            raise ValueError("epoch.overlap_sec must be smaller than epoch.length_sec.")

    def as_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.data)


def default_config_path() -> Path:
    """Path to the config.yaml shipped in the repo (config/config.yaml)."""
    return Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"


def load_config(path: Optional[str | Path] = None) -> Config:
    """Load config from ``path``, or the repo's default config/config.yaml."""
    if path is None:
        p = default_config_path()
        if p.exists():
            return Config.from_yaml(p)
        return Config.from_dict({}, project_root=str(Path.cwd()))
    return Config.from_yaml(path)
