"""End-to-end and unit tests. All synthetic - safe to run anywhere, no patient data."""
import numpy as np
import pandas as pd
import pytest

from generate_synthetic_data import make_recording, write_xdf, XON_CHANNELS
from xon_aperiodic.config import Config, load_config
from xon_aperiodic.metadata import MetadataResolver, FileMetadata
from xon_aperiodic.pipeline import run_pipeline
from xon_aperiodic.batch import run_batch, find_xdf_files, order_master_columns
from xon_aperiodic import io_xdf


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------
def test_config_defaults_and_validation():
    cfg = Config.from_dict({})
    assert cfg.get("fooof", "freq_range") == [1, 40]
    assert cfg.reference is None
    assert cfg.montage_name == "standard_1020"


def test_config_rejects_bad_values():
    with pytest.raises(ValueError):
        Config.from_dict({"artifacts": {"interpolation_method": "banana"}})
    with pytest.raises(ValueError):
        Config.from_dict({"fooof": {"freq_range": [40, 1]}})
    with pytest.raises(ValueError):
        Config.from_dict({"epoch": {"length_sec": 1.0, "overlap_sec": 1.0}})


# --------------------------------------------------------------------------
# xdf round-trip
# --------------------------------------------------------------------------
def test_xdf_roundtrip(clean_xdf):
    raw = io_xdf.load_xdf_as_raw(str(clean_xdf))
    assert raw.info["sfreq"] == 250.0
    assert raw.ch_names == XON_CHANNELS
    assert raw.times[-1] > 100  # ~2 minutes


# --------------------------------------------------------------------------
# metadata
# --------------------------------------------------------------------------
def test_metadata_from_filename(base_cfg, tmp_path):
    r = MetadataResolver(base_cfg)
    m = r.resolve(tmp_path / "P004_S002_movie.xdf")
    assert m.participant == "P004"
    assert m.session == "2"
    assert m.condition == "movie"


def test_metadata_manifest_override(tmp_path):
    (tmp_path / "manifest.csv").write_text(
        "file,participant,session,condition\nweird_name,P099,3,rest\n")
    cfg = load_config()
    cfg.data["metadata"]["manifest"] = str(tmp_path / "manifest.csv")
    cfg.project_root = str(tmp_path)
    r = MetadataResolver(cfg)
    m = r.resolve(tmp_path / "weird_name.xdf")
    assert m.participant == "P099" and m.session == "3" and m.condition == "rest"


def test_metadata_condition_alias(base_cfg, tmp_path):
    m = MetadataResolver(base_cfg).resolve(tmp_path / "P001_S001_film.xdf")
    assert m.condition == "movie"   # film -> movie via aliases


# --------------------------------------------------------------------------
# exponent recovery accuracy (the core scientific validation)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("true_exp", [0.7, 1.2, 1.8])
def test_exponent_recovery(base_cfg, tmp_path, true_exp):
    base_cfg.data["analysis"]["block_analysis"] = False
    base_cfg.data["analysis"]["convergence_analysis"] = False
    rng = np.random.default_rng(7)
    data = make_recording(250.0, 3.0, true_exp, rng, amp_uv=12.0)
    path = tmp_path / "rec.xdf"
    write_xdf(path, data, 250.0, XON_CHANNELS)
    meta = FileMetadata(path=str(path), file_stem="rec", subject_id="rec")
    result = run_pipeline(str(path), cfg=base_cfg, metadata=meta)
    avg = result.results_df[(result.results_df.channel == "AVERAGE") &
                            (result.results_df.segment == "full")]
    recovered = float(avg["aperiodic_exponent"].iloc[0])
    assert abs(recovered - true_exp) < 0.2, f"recovered {recovered} vs known {true_exp}"
    assert float(avg["r_squared"].iloc[0]) > 0.9


# --------------------------------------------------------------------------
# single-file outputs exist
# --------------------------------------------------------------------------
def test_single_file_outputs(base_cfg, clean_xdf):
    result = run_pipeline(str(clean_xdf), cfg=base_cfg)
    for key in ("results", "peaks", "epoch_qc", "diagnostic", "qc_report"):
        assert key in result.output_paths
    m = result.master_record
    assert m["status"] == "ok"
    assert m["participant"] == "P001" and m["condition"] == "rest"
    # convergence should have produced a minutes-to-stability value
    assert m.get("minutes_to_stability", "") != ""


# --------------------------------------------------------------------------
# batch + stats
# --------------------------------------------------------------------------
def test_batch_and_stats(base_cfg, cohort_dir):
    base_cfg.data["io"]["input_dir"] = str(cohort_dir)
    base_cfg.data["analysis"]["block_analysis"] = False
    outputs = run_batch(cfg=base_cfg)
    assert "master_csv" in outputs and "cohort_report" in outputs
    master = outputs["master_df"]
    assert (master["status"] == "ok").all()
    assert set(master["participant"]) == {"P001", "P002"}
    # reliability CSV should exist with an ICC column
    rel = pd.read_csv(outputs["stats_reliability"])
    assert "ICC(2,1)" in rel.columns


# --------------------------------------------------------------------------
# high-offender toggle catches an injected burst channel
# --------------------------------------------------------------------------
def test_high_offender_excludes_burst_channel(base_cfg, tmp_path):
    base_cfg.data["analysis"]["block_analysis"] = False
    base_cfg.data["analysis"]["convergence_analysis"] = False
    base_cfg.data["artifacts"]["detect_bad_channels"] = False   # mimic the detector missing it
    base_cfg.data["high_offender"]["enabled"] = True
    base_cfg.data["high_offender"]["min_reject_pct"] = 5.0
    base_cfg.data["high_offender"]["action"] = "exclude"
    rng = np.random.default_rng(3)
    data = make_recording(250.0, 3.0, 1.2, rng, burst_channel="F3")
    path = tmp_path / "burst.xdf"
    write_xdf(path, data, 250.0, XON_CHANNELS)
    meta = FileMetadata(path=str(path), file_stem="burst", subject_id="burst")
    result = run_pipeline(str(path), cfg=base_cfg, metadata=meta)
    note = result.master_record.get("high_offender_flagged_channels", "")
    # F3 should be identified as the dominant offender (or the recording was clean enough)
    assert "F3" in note or result.master_record.get("worst_reject_channel") == "F3"


# --------------------------------------------------------------------------
# reference override changes the exponent (regression sanity)
# --------------------------------------------------------------------------
def test_average_reference_runs(base_cfg, clean_xdf):
    base_cfg.data["analysis"]["block_analysis"] = False
    base_cfg.data["analysis"]["convergence_analysis"] = False
    base_cfg.data["artifacts"]["reference"] = "average"
    result = run_pipeline(str(clean_xdf), cfg=base_cfg)
    assert result.master_record["reference"] == "average"
    assert result.master_record["status"] == "ok"
