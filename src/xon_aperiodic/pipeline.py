"""Run the full pipeline on ONE recording.

This is the orchestrator. It preserves the validated design of the original:
  detect bad channels -> (ICA) -> [interpolate -> re-reference -> epoch -> QC -> FOOOF]
with the bracketed sequence wrapped in a nested ``_process`` so it can be re-run:
  * PASS 1 with only variance/amplitude bad channels,
  * PASS 1b (optional) after adding high-offender channels,
  * PASS 2 (optional) after adding low-exponent channels,
so the exponent we reject on is exactly the exponent we report.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import mne
import numpy as np
import pandas as pd

from .config import Config, load_config
from .logging_utils import step, info, get_logger
from .metadata import FileMetadata, MetadataResolver
from .io_xdf import load_xdf_as_raw, safe_name
from .preprocess import (
    mark_obvious_non_eeg_channels, apply_montage, crop_recording, apply_filter,
    detect_bad_channels, detect_flat_railing_channels, interpolate_bad_channels,
    run_ica, apply_reference, eeg_channel_names, resolve_channel,
)
from .epoching import make_awake_epochs
from .artifacts import reject_artifacts
from .spectral import fit_segment, compute_duration_curve
from . import diagnostics


@dataclass
class PipelineResult:
    """Everything one file produced (returned to the batch layer)."""
    subject_id: str
    metadata: FileMetadata
    results_df: pd.DataFrame
    master_record: Dict[str, Any]
    duration_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    output_paths: Dict[str, str] = field(default_factory=dict)


def _build_master_record(meta: FileMetadata, input_xdf: str, settings_cols: Dict[str, Any],
                         res: Dict[str, Any], full_rows: List[Dict[str, Any]],
                         raw_after_ica: mne.io.BaseRaw, interpolated_channels: List[str],
                         excluded_channels: List[str], exponent_flagged: List[str]) -> Dict[str, Any]:
    """Flatten EVERYTHING about one file into a single wide row (the master CSV)."""
    qc_stats = dict(res.get("qc_stats", {}) or {})
    per_channel_hits = qc_stats.pop("per_channel_hits", {}) or {}
    try:
        total_rejected = int(qc_stats.get("epochs_before_qc", 0)) - int(qc_stats.get("epochs_final_clean", 0))
    except Exception:
        total_rejected = 0
    avg_row = next((r for r in full_rows if r.get("channel") == "AVERAGE"), {})

    record: Dict[str, Any] = dict(settings_cols)
    record.update(dict(
        subject_id=meta.subject_id, file_stem=Path(input_xdf).stem,
        participant=meta.participant, session=meta.session, condition=meta.condition,
        status="ok", error_message="",
    ))
    record.update(qc_stats)
    record.update(dict(
        clean_minutes=avg_row.get("clean_minutes", ""),
        n_interpolated=len(interpolated_channels), n_excluded=len(excluded_channels),
        n_exponent_flagged=len(exponent_flagged),
        AVERAGE_exponent=avg_row.get("aperiodic_exponent", ""),
        AVERAGE_exponent_sd=avg_row.get("aperiodic_exponent_sd", ""),
        AVERAGE_offset=avg_row.get("aperiodic_offset", ""),
        AVERAGE_r_squared=avg_row.get("r_squared", ""),
        AVERAGE_n_channels_averaged=avg_row.get("n_channels_averaged", ""),
    ))

    logvar_by_ch: Dict[str, float] = {}
    try:
        eeg_names = eeg_channel_names(raw_after_ica, exclude_bads=False)
        raw_data = raw_after_ica.get_data(picks=eeg_names)
        logvar_by_ch = {n: float(np.log(np.var(raw_data[i]) + 1e-30)) for i, n in enumerate(eeg_names)}
    except Exception:
        logvar_by_ch = {}

    interp_set = {c.upper() for c in interpolated_channels}
    excl_set = {c.upper() for c in excluded_channels}
    ch_total_hits: Dict[str, int] = {}
    for r in full_rows:
        ch = r.get("channel")
        if not ch or ch == "AVERAGE":
            continue
        record[f"{ch}_exponent"] = r.get("aperiodic_exponent", "")
        record[f"{ch}_offset"] = r.get("aperiodic_offset", "")
        record[f"{ch}_r2"] = r.get("r_squared", "")
        record[f"{ch}_fit_error"] = r.get("fit_error", "")
        record[f"{ch}_n_peaks"] = r.get("n_peaks_detected", "")
        record[f"{ch}_logvar"] = round(logvar_by_ch[ch], 4) if ch in logvar_by_ch else ""
        record[f"{ch}_interpolated"] = ch.upper() in interp_set
        record[f"{ch}_excluded"] = ch.upper() in excl_set
        record[f"{ch}_fit_note"] = r.get("error", "")
        h = per_channel_hits.get(ch, {}) or {}
        amp_flat_h, grad_h = int(h.get("amp_flat", 0)), int(h.get("gradient", 0))
        var_h, mus_h = int(h.get("variance", 0)), int(h.get("muscle", 0))
        total_h = amp_flat_h + grad_h + var_h + mus_h
        ch_total_hits[ch] = total_h
        record[f"{ch}_amp_flat_hits"] = amp_flat_h
        record[f"{ch}_gradient_hits"] = grad_h
        record[f"{ch}_variance_hits"] = var_h
        record[f"{ch}_muscle_hits"] = mus_h
        record[f"{ch}_total_reject_hits"] = total_h
        record[f"{ch}_pct_of_rejected_epochs"] = (
            round(100.0 * total_h / total_rejected, 2) if total_rejected > 0 else 0.0)

    if ch_total_hits and total_rejected > 0 and max(ch_total_hits.values()) > 0:
        worst = max(ch_total_hits, key=ch_total_hits.get)
        record["worst_reject_channel"] = worst
        record["worst_reject_channel_share"] = round(100.0 * ch_total_hits[worst] / total_rejected, 2)
    else:
        record["worst_reject_channel"] = ""
        record["worst_reject_channel_share"] = 0.0
    return record


def run_pipeline(input_xdf: str, cfg: Optional[Config] = None,
                 metadata: Optional[FileMetadata] = None) -> PipelineResult:
    """Process one .xdf file end-to-end and write its per-file outputs."""
    cfg = cfg or load_config()
    if metadata is None:
        metadata = MetadataResolver(cfg).resolve(input_xdf)
    meta = metadata
    subject_id = meta.subject_id or safe_name(input_xdf)

    # --- pull every setting out of cfg once, for readability ---
    A = cfg.section("artifacts")
    out_dir = str(cfg.output_dir)
    # per-recording (granular) outputs live in a sub-folder so the top level stays clean
    per_dir = os.path.join(out_dir, "per_recording")
    os.makedirs(per_dir, exist_ok=True)
    epoch_len = float(cfg.get("epoch", "length_sec"))
    epoch_overlap = float(cfg.get("epoch", "overlap_sec"))
    fooof_range = cfg.get("fooof", "freq_range")
    fooof_settings = cfg.fooof_settings
    detect_bad_exp = bool(cfg.get("exponent_rejection", "enabled"))
    exp_threshold = float(cfg.get("exponent_rejection", "threshold"))
    ho = cfg.section("high_offender")
    an = cfg.section("analysis")
    analyze_all = bool(cfg.get("xdf", "analyze_all_channels", True))
    force_channel = cfg.get("xdf", "channel", None)

    # ---------------- load & prepare ----------------
    raw = load_xdf_as_raw(input_xdf, data_units=cfg.get("xdf", "data_units"),
                          stream_name=cfg.get("xdf", "stream_name"),
                          stream_type=cfg.get("xdf", "stream_type"))
    raw = mark_obvious_non_eeg_channels(raw)
    raw = crop_recording(raw, cfg.get("crop", "start_sec"), cfg.get("crop", "stop_sec"))
    raw = apply_montage(raw, cfg.montage_name)

    duration_min = raw.times[-1] / 60.0
    expected = cfg.get("crop", "expected_duration_min")
    if expected is not None and abs(duration_min - float(expected)) > 2.0:
        info(f"\n  Warning: selected stream is {duration_min:.2f} min, not close to "
             f"expected {float(expected):.1f} min.")

    raw = apply_filter(raw, cfg.get("filter", "high_pass_hz"), cfg.get("filter", "notch_freq_hz"))

    if A.get("detect_bad_channels", True):
        raw = detect_bad_channels(raw, float(A["bad_channel_zscore"]))
        if A.get("use_annotate_amplitude", True):
            raw = detect_flat_railing_channels(raw, float(A["flat_threshold_uv"]),
                                               float(A["amplitude_threshold_uv"]))
    if A.get("run_ica", False):
        raw = run_ica(raw, n_components=A.get("ica_n_components"), method=A.get("ica_method"),
                      random_state=int(A.get("ica_random_state", 97)),
                      muscle_thresh=float(A.get("ica_muscle_threshold", 0.8)),
                      eog_thresh=float(A.get("ica_eog_threshold", 3.0)),
                      ecg_thresh=float(A.get("ica_ecg_threshold", 0.3)))

    raw_after_ica = raw.copy()

    def _process(raw_in: mne.io.BaseRaw, exclude_no_interp: Optional[List[str]] = None) -> Dict[str, Any]:
        exclude_no_interp = [c for c in (exclude_no_interp or []) if c in raw_in.ch_names]
        interpolated: List[str] = []
        if A.get("interpolate_bad_channels", True):
            held = [c for c in exclude_no_interp if c in raw_in.info["bads"]]
            raw_in.info["bads"] = [b for b in raw_in.info["bads"] if b not in held]
            raw_in, interpolated = interpolate_bad_channels(raw_in, A.get("interpolation_method", "average"))
            for c in held:
                if c not in raw_in.info["bads"]:
                    raw_in.info["bads"].append(c)
        if cfg.reference is not None:
            raw_in = apply_reference(raw_in, cfg.reference, exclude_from_average=interpolated)
        excluded = list(raw_in.info["bads"])

        if not analyze_all and force_channel is not None:
            keep = resolve_channel(raw_in, force_channel)
            raw_in.info["bads"] = [b for b in raw_in.info["bads"] if b != keep]
            raw_in = raw_in.copy().pick([keep])
            info(f"\n  Single-channel mode: analyzing only {keep}.")

        epochs, analyzed = make_awake_epochs(raw_in, epoch_len, epoch_overlap)
        clean, qc, qc_stats = reject_artifacts(
            epochs, float(A["amplitude_threshold_uv"]), float(A["flat_threshold_uv"]),
            A.get("variance_zscore_threshold"), A.get("muscle_zscore_threshold"),
            float(A["muscle_hf_hz"]), A.get("gradient_threshold_uv_per_ms"),
            ignore_channels=interpolated)
        f_rows, f_peaks, f_freqs, f_psd, f_fm, f_ch = fit_segment(
            clean, subject_id, "full", 0.0, round(len(clean) * epoch_len / 60.0, 4),
            epoch_len, fooof_range, fooof_settings, interpolated_channels=interpolated)
        return dict(interpolated_channels=interpolated, excluded_channels=excluded,
                    analyzed_channels=analyzed, clean_epochs=clean, qc_df=qc, qc_stats=qc_stats,
                    full_rows=f_rows, full_peaks=f_peaks, freqs=f_freqs, psd_2d=f_psd,
                    fm_by_channel=f_fm, ch_names=f_ch)

    # PASS 1
    res = _process(raw_after_ica.copy())

    # PASS 1b: high-offender channel rejection (EXPERIMENTAL, off by default)
    high_offender_flagged: List[str] = []
    high_offender_note = ""
    if ho.get("enabled", False):
        step("STEP 4b: High-offender channel rejection (EXPERIMENTAL, on rejection share)")
        qc1 = res.get("qc_stats", {}) or {}
        pch = qc1.get("per_channel_hits", {}) or {}
        total_rej = int(qc1.get("epochs_before_qc", 0)) - int(qc1.get("epochs_final_clean", 0))
        pct_rej = float(qc1.get("pct_epochs_rejected", 0.0) or 0.0)
        already_bad = {c.upper() for c in (res["interpolated_channels"] + res["excluded_channels"])}
        share_thr = float(ho.get("share_threshold", 50.0))
        min_rej = float(ho.get("min_reject_pct", 15.0))
        action = "exclude" if ho.get("action") == "exclude" else "interpolate"
        if total_rej <= 0 or not pch:
            info("  No rejected epochs to attribute; keeping pass-1 result.")
        elif pct_rej < min_rej:
            high_offender_note = f"skipped (only {pct_rej:.1f}% rejected < {min_rej:.0f}% gate)"
            info(f"  Session only {pct_rej:.1f}% rejected (< {min_rej:.0f}% gate); keeping all channels.")
        else:
            shares = {ch: 100.0 * (int(h.get("amp_flat", 0)) + int(h.get("gradient", 0)) +
                                   int(h.get("variance", 0)) + int(h.get("muscle", 0))) / total_rej
                      for ch, h in pch.items()}
            candidates = sorted([ch for ch, s in shares.items()
                                 if s > share_thr and ch.upper() not in already_bad],
                                key=lambda c: shares[c], reverse=True)
            if not candidates:
                info(f"  No channel above {share_thr:.0f}% rejection share; keeping pass-1 result.")
            else:
                good_now = len(eeg_channel_names(raw_after_ica, exclude_bads=True))
                if good_now - len(candidates) < 3:
                    high_offender_note = f"refused ({candidates} would leave <3 good channels)"
                    info(f"  {candidates} exceed the share threshold, but dropping them would leave "
                         "< 3 good channels. Refusing - inspect this recording manually.")
                else:
                    for ch in candidates:
                        if ch not in raw_after_ica.info["bads"]:
                            raw_after_ica.info["bads"].append(ch)
                    high_offender_flagged = candidates
                    high_offender_note = "; ".join(f"{c}={shares[c]:.0f}%" for c in candidates)
                    info(f"  Flagging {candidates} ({high_offender_note}) as high offenders; "
                         f"action={action}; re-running.")
                    if action == "exclude":
                        res = _process(raw_after_ica.copy(), exclude_no_interp=candidates)
                    else:
                        res = _process(raw_after_ica.copy())

    # PASS 2: exponent-based channel rejection (reject on the FINAL exponent)
    exponent_flagged: List[str] = []
    if detect_bad_exp:
        candidates = [r["channel"] for r in res["full_rows"]
                      if r.get("channel") != "AVERAGE" and not r.get("interpolated", False)
                      and r.get("aperiodic_exponent") is not None
                      and r["aperiodic_exponent"] < exp_threshold]
        step("STEP 6b: Exponent-based channel rejection (on final fit)")
        if not candidates:
            info(f"  No non-interpolated channel below exponent {exp_threshold}; keeping pass-1 result.")
        else:
            good_now = len(eeg_channel_names(raw_after_ica, exclude_bads=True))
            if good_now - len(candidates) < 3:
                info(f"  {candidates} below threshold, but rejecting them would leave < 3 good "
                     "channels. Refusing - inspect this recording manually.")
            else:
                for ch in candidates:
                    if ch not in raw_after_ica.info["bads"]:
                        raw_after_ica.info["bads"].append(ch)
                exponent_flagged = candidates
                info(f"  Rejecting {candidates} (final exponent < {exp_threshold}); "
                     "re-running with them interpolated.")
                res = _process(raw_after_ica.copy())

    interpolated_channels = res["interpolated_channels"]
    excluded_channels = res["excluded_channels"]
    analyzed_channels = res["analyzed_channels"]
    clean_epochs = res["clean_epochs"]
    qc_df = res["qc_df"]
    bad_channels = sorted(set(interpolated_channels) | set(excluded_channels))

    qc_path = os.path.join(per_dir, f"epoch_qc_{subject_id}.csv")
    qc_df.to_csv(qc_path, index=False)

    settings_cols = dict(
        input_file=input_xdf, original_duration_min=round(duration_min, 4),
        data_units_assumed=cfg.get("xdf", "data_units"),
        epoch_length_sec=epoch_len, epoch_overlap_sec=epoch_overlap,
        high_pass_hz=cfg.get("filter", "high_pass_hz"), notch_freq_hz=cfg.get("filter", "notch_freq_hz"),
        fooof_freq_lo=fooof_range[0], fooof_freq_hi=fooof_range[1],
        aperiodic_mode=fooof_settings.get("aperiodic_mode", "fixed"),
        amplitude_threshold_uv=A["amplitude_threshold_uv"],
        gradient_threshold_uv_per_ms=A.get("gradient_threshold_uv_per_ms") if A.get("gradient_threshold_uv_per_ms") is not None else "",
        flat_threshold_uv=A["flat_threshold_uv"],
        variance_zscore_threshold=A.get("variance_zscore_threshold"),
        muscle_zscore_threshold=A.get("muscle_zscore_threshold"), muscle_hf_hz=A["muscle_hf_hz"],
        ica_applied=bool(A.get("run_ica", False)),
        reference=("ear" if cfg.reference is None else str(cfg.reference)),
        interpolation_method=A.get("interpolation_method") if A.get("interpolate_bad_channels", True) else "",
        montage=cfg.montage_name or "",
        bad_channels=";".join(bad_channels) if bad_channels else "",
        interpolated_channels=";".join(interpolated_channels) if interpolated_channels else "",
        excluded_channels=";".join(excluded_channels) if excluded_channels else "",
        exponent_flagged_channels=";".join(exponent_flagged) if exponent_flagged else "",
        exponent_reject_threshold=exp_threshold if detect_bad_exp else "",
        high_offender_rejection=bool(ho.get("enabled", False)),
        high_offender_share_threshold=ho.get("share_threshold") if ho.get("enabled") else "",
        high_offender_min_reject_pct=ho.get("min_reject_pct") if ho.get("enabled") else "",
        high_offender_action=ho.get("action") if ho.get("enabled") else "",
        high_offender_flagged_channels=high_offender_note,
        n_channels_analyzed=len(analyzed_channels),
    )

    all_rows: List[Dict[str, Any]] = []
    all_peaks: List[pd.DataFrame] = []
    full_rows = res["full_rows"]
    for row in full_rows:
        row.update(settings_cols)
    all_rows.extend(full_rows)
    all_peaks.append(res["full_peaks"])

    diagnostic_path = diagnostics.save_diagnostic_plot(
        res["freqs"], res["psd_2d"], res["fm_by_channel"], res["ch_names"], full_rows, qc_df,
        subject_id, per_dir, interpolated_channels=interpolated_channels,
        excluded_channels=excluded_channels)

    # ---- block analysis ----
    if an.get("block_analysis", True):
        block_len_min = float(an.get("block_length_min", 5.0))
        block_epochs = int(round((block_len_min * 60.0) / epoch_len))
        n_full_blocks = len(clean_epochs) // block_epochs if block_epochs > 0 else 0
        step("STEP 7: Optional block analysis")
        info(f"  Block length: {block_len_min:.1f} min")
        info(f"  Full clean blocks available: {n_full_blocks}")
        for b in range(n_full_blocks):
            s, e = b * block_epochs, b * block_epochs + block_epochs
            seg = clean_epochs[s:e]
            start_min, end_min = round(s * epoch_len / 60.0, 4), round(e * epoch_len / 60.0, 4)
            label = f"block_{b + 1:02d}"
            try:
                block_rows, peak_df, _, _, _, _ = fit_segment(
                    seg, subject_id, label, start_min, end_min, epoch_len, fooof_range,
                    fooof_settings, verbose=False, interpolated_channels=interpolated_channels)
                for row in block_rows:
                    row.update(settings_cols)
                all_rows.extend(block_rows)
                all_peaks.append(peak_df)
                avg = next((r for r in block_rows if r.get("channel") == "AVERAGE"), None)
                if avg is not None:
                    info(f"  {label} ({start_min:.1f}-{end_min:.1f} min): avg exponent = "
                         f"{avg['aperiodic_exponent']:.4f}")
            except Exception as exc:
                err = dict(subject_id=subject_id, channel="AVERAGE", segment=label,
                           segment_start_min=start_min, segment_end_min=end_min, error=str(exc))
                err.update(settings_cols)
                all_rows.append(err)

    # ---- duration curve (raw material for cohort reliability-vs-duration) ----
    duration_df = pd.DataFrame()
    if an.get("reliability_analysis", True):
        step("STEP 8: Duration curve (exponent vs clean minutes, all/odd/even)")
        duration_df = compute_duration_curve(
            clean_epochs, epoch_len, fooof_range, fooof_settings,
            step_sec=float(an.get("reliability_step_sec", 30.0)),
            interpolated_channels=interpolated_channels)
        if not duration_df.empty:
            dpath = os.path.join(per_dir, f"durationcurve_{subject_id}.csv")
            duration_df.to_csv(dpath, index=False)
            info(f"  Duration curve: {len(duration_df)} points up to "
                 f"{duration_df['clean_minutes'].max():.1f} min")
            diagnostics.save_duration_plot(duration_df, subject_id, per_dir)

    results_df = pd.DataFrame(all_rows)
    results_path = os.path.join(per_dir, f"aperiodic_results_{subject_id}.csv")
    results_df.to_csv(results_path, index=False)
    peaks_df = pd.concat(all_peaks, ignore_index=True) if all_peaks else pd.DataFrame()
    peaks_path = os.path.join(per_dir, f"peak_table_{subject_id}.csv")
    peaks_df.to_csv(peaks_path, index=False)
    block_plot_path = diagnostics.save_block_plot(results_df, per_dir, subject_id)

    step("DONE (this file)")
    info(f"  Channels analyzed: {len(analyzed_channels)} ({analyzed_channels})")
    if high_offender_flagged:
        info(f"  High-offender channels ({ho.get('action')}d): {high_offender_flagged}")
    if exponent_flagged:
        info(f"  Flagged for low aperiodic exponent (< {exp_threshold}): {exponent_flagged}")
    if interpolated_channels:
        info(f"  Interpolated (excluded from AVERAGE): {interpolated_channels}")
    if excluded_channels:
        info(f"  Excluded bad channels (not interpolated): {excluded_channels}")

    master_record = _build_master_record(
        meta, input_xdf, settings_cols, res, full_rows, raw_after_ica,
        interpolated_channels, excluded_channels, exponent_flagged)

    # per-file human-readable QC report
    qc_report_path = diagnostics.write_qc_report(
        subject_id, meta, master_record, res, qc_df, per_dir,
        diagnostic_path=diagnostic_path, block_plot_path=block_plot_path)

    output_paths = dict(results=results_path, peaks=peaks_path, epoch_qc=qc_path,
                        diagnostic=diagnostic_path, qc_report=qc_report_path)
    if block_plot_path:
        output_paths["block_plot"] = block_plot_path
    return PipelineResult(subject_id=subject_id, metadata=meta, results_df=results_df,
                          master_record=master_record, duration_df=duration_df,
                          output_paths=output_paths)
