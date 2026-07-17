"""Batch layer: find recordings, run each through the pipeline, and assemble the
cohort-level outputs (combined long CSV, wide master CSV, statistics, and the
cohort HTML report with publication figures).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .config import Config, load_config
from .logging_utils import setup_logging, banner, info
from .metadata import MetadataResolver
from .io_xdf import safe_name
from .pipeline import run_pipeline, PipelineResult


def find_xdf_files(input_dir: str | Path, pattern: str = "*.xdf", recursive: bool = False) -> List[Path]:
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_path}")
    if not input_path.is_dir():
        raise NotADirectoryError(f"input_dir must be a folder: {input_path}")
    files = sorted(input_path.rglob(pattern) if recursive else input_path.glob(pattern))
    files = [f for f in files if f.is_file() and not f.name.startswith(".")]
    if not files:
        raise FileNotFoundError(f"No files found in {input_path} with pattern {pattern!r}.")
    return files


MASTER_LEAD_COLS = [
    "subject_id", "file_stem", "participant", "session", "condition", "status", "error_message",
    "input_file", "original_duration_min", "clean_minutes",
    "epochs_before_qc", "epochs_after_amp_flat", "epochs_dropped_amp_flat",
    "epochs_dropped_gradient", "epochs_flagged_variance", "epochs_flagged_muscle",
    "epochs_final_clean", "pct_epochs_rejected", "pct_epochs_kept",
    "AVERAGE_exponent", "AVERAGE_exponent_sd", "AVERAGE_r_squared", "AVERAGE_n_channels_averaged",
    "n_channels_analyzed", "n_interpolated", "n_excluded", "n_exponent_flagged",
    "bad_channels", "interpolated_channels", "excluded_channels",
    "exponent_flagged_channels", "high_offender_flagged_channels",
    "worst_reject_channel", "worst_reject_channel_share",
]


def order_master_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    lead = [c for c in MASTER_LEAD_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in lead]
    return df[lead + rest]


def run_batch(cfg: Optional[Config] = None, input_files: Optional[Iterable[Path]] = None,
              run_stats: bool = True) -> Dict[str, Any]:
    """Run the whole cohort. Returns a dict of output paths and the master dataframe."""
    cfg = cfg or load_config()
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir)

    if input_files is None:
        input_files = find_xdf_files(cfg.input_dir, pattern=cfg.get("io", "file_glob", "*.xdf"),
                                     recursive=bool(cfg.get("io", "recursive", True)))
    files = list(input_files)
    resolver = MetadataResolver(cfg)

    banner(f"BATCH MODE: {len(files)} recording(s)")
    combined_rows: List[pd.DataFrame] = []
    master_records: List[Dict[str, Any]] = []
    results: List[PipelineResult] = []

    for i, fpath in enumerate(files, start=1):
        fpath_str = str(fpath)
        banner(f"FILE {i}/{len(files)}: {fpath_str}")
        meta = resolver.resolve(fpath)
        try:
            result = run_pipeline(fpath_str, cfg=cfg, metadata=meta)
            combined_rows.append(result.results_df)
            master_records.append(result.master_record)
            results.append(result)
        except Exception as exc:
            info(f"\nERROR processing {fpath_str}: {exc}")
            combined_rows.append(pd.DataFrame([{
                "subject_id": meta.subject_id, "input_file": fpath_str, "error": str(exc)}]))
            master_records.append(dict(
                subject_id=meta.subject_id, input_file=fpath_str, file_stem=Path(fpath_str).stem,
                participant=meta.participant, session=meta.session, condition=meta.condition,
                status="error", error_message=str(exc)))

    combined_df = pd.concat(combined_rows, ignore_index=True) if combined_rows else pd.DataFrame()
    combined_path = out_dir / (cfg.get("io", "combined_name", "combined_aperiodic_results.csv") or "combined_aperiodic_results.csv")
    combined_df.to_csv(combined_path, index=False)

    master_df = order_master_columns(pd.DataFrame(master_records))
    master_path = out_dir / "master_everything.csv"
    master_df.to_csv(master_path, index=False)

    outputs = dict(combined_csv=str(combined_path), master_csv=str(master_path))

    banner("BATCH DONE")
    info(f"Combined results CSV (long): {combined_path}")
    info(f"MASTER CSV (one wide row per file): {master_path}")
    n_err = sum(1 for m in master_records if m.get("status") == "error")
    if n_err:
        info(f"  {n_err}/{len(files)} file(s) errored - see status=='error' rows in the master CSV.")

    # cohort statistics + report
    if run_stats and cfg.get("stats", "enabled", True):
        from . import reporting
        stats_outputs = reporting.build_cohort_outputs(cfg, master_df, results, out_dir)
        outputs.update(stats_outputs)

    outputs["master_df"] = master_df
    return outputs
