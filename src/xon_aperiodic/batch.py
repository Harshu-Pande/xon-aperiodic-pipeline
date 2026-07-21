"""Batch layer: find recordings, run each through the pipeline, and assemble the
cohort-level outputs (combined long CSV, wide master CSV, statistics, and the
cohort HTML report with publication figures).
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


def output_has_results(output_dir: str | Path) -> bool:
    """True if this folder already holds a previous run's results."""
    d = Path(output_dir)
    return (d / "cohort_report.html").exists() or (d / "master_everything.csv").exists()


def timestamped_sibling(output_dir: str | Path) -> Path:
    """A fresh 'save a copy' folder next to the chosen one, e.g. outputs_2026-07-18_143022."""
    d = Path(output_dir)
    return d.parent / f"{d.name}_{datetime.now():%Y%m%d_%H%M%S}"

from .config import Config, load_config
from .logging_utils import setup_logging, banner, info
from .metadata import MetadataResolver
from .io_xdf import safe_name
from .pipeline import run_pipeline, PipelineResult


# Extensions that are clearly not EEG recordings, skipped when the pattern is broad ("*").
_NON_DATA_EXTS = {".csv", ".tsv", ".txt", ".md", ".html", ".htm", ".png", ".jpg", ".jpeg",
                  ".gif", ".pdf", ".json", ".yaml", ".yml", ".log", ".zip", ".gz", ".xlsx",
                  ".xls", ".docx", ".pptx", ".py", ".ipynb", ".ds_store"}


def find_xdf_files(input_dir: str | Path, pattern: str = "*", recursive: bool = False) -> List[Path]:
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_path}")
    if not input_path.is_dir():
        raise NotADirectoryError(f"input_dir must be a folder: {input_path}")
    files = sorted(input_path.rglob(pattern) if recursive else input_path.glob(pattern))
    files = [f for f in files if f.is_file() and not f.name.startswith(".")
             and f.suffix.lower() not in _NON_DATA_EXTS]
    if not files:
        raise FileNotFoundError(f"No recordings found in {input_path} with pattern {pattern!r}.")
    return files


MASTER_LEAD_COLS = [
    "subject_id", "file_stem", "participant", "session", "condition", "status", "error_message",
    "input_file", "original_duration_min", "clean_minutes",
    "epochs_before_qc", "epochs_after_amp_flat", "epochs_dropped_amp_flat",
    "epochs_dropped_gradient", "epochs_flagged_variance", "epochs_flagged_muscle",
    "epochs_final_clean", "pct_epochs_rejected", "pct_epochs_kept",
    "AVERAGE_exponent", "AVERAGE_exponent_sd", "AVERAGE_r_squared", "AVERAGE_n_channels_averaged",
    "minutes_to_stabilize", "minutes_to_converge",
    "n_channels_analyzed", "n_interpolated", "n_excluded", "n_exponent_flagged",
    "bad_channels", "interpolated_channels", "excluded_channels",
    "exponent_flagged_channels", "screened_channels",
    "worst_reject_channel", "worst_reject_channel_share",
]


def order_master_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    lead = [c for c in MASTER_LEAD_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in lead]
    return df[lead + rest]


def _process_file(payload):
    """Top-level worker (must be picklable for parallel processing)."""
    fpath_str, cfg, meta = payload
    try:
        return ("ok", meta, run_pipeline(fpath_str, cfg=cfg, metadata=meta))
    except Exception as exc:  # noqa: BLE001
        return ("err", meta, str(exc))


def _resolve_n_jobs(cfg: Config, n_files: int) -> int:
    setting = cfg.get("performance", "n_jobs", "auto")
    cap = int(cfg.get("performance", "max_workers", 6) or 6)
    cpu = os.cpu_count() or 2
    if isinstance(setting, int) or (isinstance(setting, str) and str(setting).isdigit()):
        n = int(setting)
    else:
        n = max(1, cpu - 1)         # "auto": leave one core free
    return max(1, min(n, cap, n_files))


def run_batch(cfg: Optional[Config] = None, input_files: Optional[Iterable[Path]] = None,
              run_stats: bool = True) -> Dict[str, Any]:
    """Run the whole cohort. Returns a dict of output paths and the master dataframe."""
    cfg = cfg or load_config()
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir / "logs")

    if input_files is None:
        input_files = find_xdf_files(cfg.input_dir, pattern=cfg.get("io", "file_glob", "*.xdf"),
                                     recursive=bool(cfg.get("io", "recursive", True)))
    files = list(input_files)
    resolver = MetadataResolver(cfg)

    metas = [resolver.resolve(f) for f in files]
    payloads = [(str(f), cfg, m) for f, m in zip(files, metas)]
    n_jobs = _resolve_n_jobs(cfg, len(files))
    banner(f"BATCH MODE: {len(files)} recording(s), {n_jobs} parallel worker(s)")

    outcomes: List[Any] = [None] * len(files)
    if n_jobs <= 1:
        for i, pl in enumerate(payloads):
            info(f"[{i + 1}/{len(files)}] {metas[i].subject_id} ...")
            outcomes[i] = _process_file(pl)
    else:
        # keep each worker single-threaded so N workers don't oversubscribe the CPU
        for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            os.environ.setdefault(v, "1")
        done = 0
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futs = {ex.submit(_process_file, pl): i for i, pl in enumerate(payloads)}
            for fut in as_completed(futs):
                i = futs[fut]
                outcomes[i] = fut.result()
                done += 1
                status, meta, _ = outcomes[i]
                info(f"  [{done}/{len(files)}] {meta.subject_id}: "
                     f"{'done' if status == 'ok' else 'ERROR'}")

    combined_rows: List[pd.DataFrame] = []
    master_records: List[Dict[str, Any]] = []
    results: List[PipelineResult] = []
    for (status, meta, payload) in outcomes:
        if status == "ok":
            combined_rows.append(payload.results_df)
            master_records.append(payload.master_record)
            results.append(payload)
        else:
            info(f"ERROR processing {meta.path}: {payload}")
            combined_rows.append(pd.DataFrame([{
                "subject_id": meta.subject_id, "input_file": meta.path, "error": payload}]))
            master_records.append(dict(
                subject_id=meta.subject_id, input_file=meta.path, file_stem=Path(meta.path).stem,
                participant=meta.participant, session=meta.session, condition=meta.condition,
                status="error", error_message=payload))

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
