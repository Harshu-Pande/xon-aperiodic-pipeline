"""Per-file diagnostics: the multi-panel diagnostic PNG, the block-over-time plot,
the convergence plot, and a self-contained HTML QC report so a human can eyeball
exactly what ran, what got cut and why, and whether the fit is trustworthy - all
without opening a CSV.
"""
from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_diagnostic_plot(freqs, psd_2d, fm_by_channel, ch_names, rows, qc_df, subject_id,
                         output_dir, interpolated_channels: Sequence[str] = (),
                         excluded_channels: Sequence[str] = ()) -> str:
    """Three panels: all-channel PSD, per-channel exponents, epoch QC counts."""
    interp_set = {str(c).upper() for c in interpolated_channels}
    excl_set = {str(c).upper() for c in excluded_channels}
    cmap = plt.get_cmap("viridis")
    n_ch = len(ch_names)
    colors = [cmap(i / max(n_ch - 1, 1)) for i in range(n_ch)]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"Xon aperiodic pipeline | {subject_id} | {n_ch} channels", fontsize=13)

    for ci, channel in enumerate(ch_names):
        psd_uv = psd_2d[ci] * 1e12
        good = np.isfinite(psd_uv) & (psd_uv > 0)
        axes[0].semilogy(freqs[good], psd_uv[good], linewidth=1.0, color=colors[ci], label=channel)
    axes[0].set_title("Average PSD (all channels)")
    axes[0].set_xlabel("Frequency (Hz)")
    axes[0].set_ylabel("Power (uV^2/Hz)")
    axes[0].grid(True, alpha=0.3)
    if n_ch <= 12:
        axes[0].legend(fontsize=7, ncol=2)

    ch_rows = [r for r in rows if r.get("channel") not in (None, "AVERAGE") and "aperiodic_exponent" in r]
    bar_names = [r["channel"] for r in ch_rows]
    bar_exps = [r["aperiodic_exponent"] for r in ch_rows]
    excluded_only = [c for c in excluded_channels if c not in bar_names]
    all_bar_names = bar_names + list(excluded_only)
    all_bar_exps = bar_exps + [0.0] * len(excluded_only)
    for i, name in enumerate(all_bar_names):
        is_interp = name.upper() in interp_set
        is_excl = name.upper() in excl_set and name in excluded_only
        color = "lightgray" if is_excl else (colors[ch_names.index(name)] if name in ch_names else "gray")
        axes[1].bar(name, all_bar_exps[i], color=color, hatch="///" if is_interp else None,
                    edgecolor="black" if (is_interp or is_excl) else None)
    avg_rows = [r for r in rows if r.get("channel") == "AVERAGE"]
    legend_handles = []
    if avg_rows:
        avg_exp = avg_rows[0]["aperiodic_exponent"]
        axes[1].axhline(avg_exp, linestyle="--", color="red", label=f"average = {avg_exp:.3f}")
    if interp_set:
        legend_handles.append(mpatches.Patch(facecolor="white", hatch="///", edgecolor="black",
                                             label="interpolated (excl. from avg)"))
    if excluded_only:
        legend_handles.append(mpatches.Patch(facecolor="lightgray", edgecolor="black", label="excluded (bad)"))
    handles, labels = axes[1].get_legend_handles_labels()
    if handles or legend_handles:
        axes[1].legend(handles=handles + legend_handles, fontsize=7)
    axes[1].set_title("Aperiodic exponent per channel")
    axes[1].set_ylabel("Aperiodic exponent")
    axes[1].tick_params(axis="x", rotation=45, labelsize=7)
    axes[1].grid(True, alpha=0.3, axis="y")

    kept = int(qc_df["kept"].sum()) if "kept" in qc_df else 0
    rejected = int(len(qc_df) - kept)
    axes[2].bar(["Kept", "Rejected"], [kept, rejected], color=["#2a9d8f", "#e76f51"])
    axes[2].set_title("Epoch QC (shared across channels)")
    axes[2].set_ylabel("Epoch count")
    axes[2].grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    out_path = os.path.join(output_dir, f"diagnostic_{subject_id}.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_block_plot(results_df: pd.DataFrame, output_dir: str, subject_id: str) -> Optional[str]:
    if "segment" not in results_df or "aperiodic_exponent" not in results_df:
        return None
    block_df = results_df[results_df["segment"].astype(str).str.startswith("block_")].copy()
    block_df = block_df.dropna(subset=["aperiodic_exponent", "segment_start_min"])
    if block_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 5))
    per_ch = block_df[block_df["channel"] != "AVERAGE"]
    cmap = plt.get_cmap("viridis")
    channels = sorted(per_ch["channel"].unique())
    for ci, channel in enumerate(channels):
        cdf = per_ch[per_ch["channel"] == channel].sort_values("segment_start_min")
        if len(cdf) >= 2:
            ax.plot(cdf["segment_start_min"], cdf["aperiodic_exponent"], linewidth=1.0, alpha=0.5,
                    color=cmap(ci / max(len(channels) - 1, 1)), label=channel)
    avg_df = block_df[block_df["channel"] == "AVERAGE"].sort_values("segment_start_min")
    if len(avg_df) >= 2:
        ax.plot(avg_df["segment_start_min"], avg_df["aperiodic_exponent"], marker="o",
                linewidth=2.5, color="black", label="channel average")
    elif len(avg_df) < 2 and len(channels) == 0:
        plt.close(fig)
        return None
    full_avg = results_df[(results_df["segment"] == "full") & (results_df["channel"] == "AVERAGE")]
    if len(full_avg) == 1 and pd.notna(full_avg["aperiodic_exponent"].iloc[0]):
        ax.axhline(float(full_avg["aperiodic_exponent"].iloc[0]), linestyle="--", color="red",
                   label="full recording (avg)")
    ax.set_xlabel("Clean-data segment start time (min)")
    ax.set_ylabel("Aperiodic exponent")
    ax.set_title("Aperiodic exponent across the awake recording")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    out_path = os.path.join(output_dir, f"block_exponents_{subject_id}.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_convergence_plot(conv_df: pd.DataFrame, summary: Dict[str, Any], subject_id: str,
                          output_dir: str) -> Optional[str]:
    if conv_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(conv_df["clean_minutes"], conv_df["aperiodic_exponent"], marker="o", color="#264653")
    target = summary.get("full_exponent")
    tol = summary.get("convergence_tolerance", 0.1)
    if target is not None:
        ax.axhline(target, linestyle="--", color="red", label=f"full-recording = {target:.3f}")
        ax.axhspan(target - tol, target + tol, color="red", alpha=0.1, label=f"+/-{tol} band")
    mts = summary.get("minutes_to_stability", "")
    if mts not in ("", None):
        ax.axvline(float(mts), linestyle=":", color="green", linewidth=2,
                   label=f"stable by {float(mts):.2f} min")
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Running aperiodic exponent (channel average)")
    ax.set_title(f"How few minutes are enough? | {subject_id}")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path = os.path.join(output_dir, f"convergence_{subject_id}.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# HTML QC report
# ---------------------------------------------------------------------------
def _row(label: str, value: Any) -> str:
    return f"<tr><td class='k'>{html.escape(str(label))}</td><td>{html.escape(str(value))}</td></tr>"


def write_qc_report(subject_id: str, meta, master_record: Dict[str, Any], res: Dict[str, Any],
                    qc_df: pd.DataFrame, output_dir: str, diagnostic_path: Optional[str] = None,
                    block_plot_path: Optional[str] = None) -> str:
    """One self-contained HTML page summarising this recording's run and quality."""
    m = master_record
    qc_stats = res.get("qc_stats", {}) or {}
    conv_img = os.path.join(output_dir, f"convergence_{subject_id}.png")

    def img_tag(path: Optional[str]) -> str:
        if path and os.path.exists(path):
            return f"<img src='{html.escape(os.path.basename(path))}' style='max-width:100%;border:1px solid #ddd;border-radius:6px;margin:8px 0'>"
        return ""

    # verdict heuristics for a quick read
    pct_rej = float(qc_stats.get("pct_epochs_rejected", 0) or 0)
    r2 = m.get("AVERAGE_r_squared", "")
    try:
        r2f = float(r2)
    except Exception:
        r2f = float("nan")
    flags = []
    if pct_rej >= 50:
        flags.append(f"High rejection ({pct_rej:.0f}% of epochs dropped) - check the offender channel below.")
    if not np.isnan(r2f) and r2f < 0.9:
        flags.append(f"Fit quality is modest (avg r^2 = {r2f:.2f}); interpret the exponent cautiously.")
    if m.get("n_excluded", 0):
        flags.append(f"{m.get('n_excluded')} channel(s) excluded (not interpolated).")
    verdict = "Looks clean." if not flags else " ".join(flags)
    verdict_color = "#2a9d8f" if not flags else "#e76f51"

    ident = "".join(_row(k, v) for k, v in [
        ("Participant", meta.participant or "-"), ("Session", meta.session or "-"),
        ("Condition", meta.condition), ("Subject id", subject_id),
        ("Source file", os.path.basename(m.get("input_file", ""))),
        ("Original duration (min)", m.get("original_duration_min", "")),
        ("Clean minutes analysed", m.get("clean_minutes", "")),
    ])
    headline = "".join(_row(k, v) for k, v in [
        ("AVERAGE aperiodic exponent", m.get("AVERAGE_exponent", "")),
        ("Exponent SD across channels", m.get("AVERAGE_exponent_sd", "")),
        ("Average fit r^2", m.get("AVERAGE_r_squared", "")),
        ("Channels averaged", m.get("AVERAGE_n_channels_averaged", "")),
        ("Minutes to stability", m.get("minutes_to_stability", "")),
    ])
    qc_tbl = "".join(_row(k, qc_stats.get(k, "")) for k in [
        "epochs_before_qc", "epochs_dropped_amp_flat", "epochs_dropped_gradient",
        "epochs_flagged_variance", "epochs_flagged_muscle", "epochs_final_clean",
        "pct_epochs_rejected", "pct_epochs_kept"])
    steps = "".join(_row(k, v) for k, v in [
        ("High-pass (Hz)", m.get("high_pass_hz", "")), ("Notch (Hz)", m.get("notch_freq_hz", "")),
        ("Montage", m.get("montage", "")), ("Reference", m.get("reference", "")),
        ("Interpolation", m.get("interpolation_method", "")),
        ("FOOOF range (Hz)", f"{m.get('fooof_freq_lo','')}-{m.get('fooof_freq_hi','')}"),
        ("Aperiodic mode", m.get("aperiodic_mode", "")),
        ("Bad channels", m.get("bad_channels", "") or "none"),
        ("Interpolated", m.get("interpolated_channels", "") or "none"),
        ("Excluded", m.get("excluded_channels", "") or "none"),
        ("Exponent-flagged", m.get("exponent_flagged_channels", "") or "none"),
        ("Worst offender channel", f"{m.get('worst_reject_channel','') or '-'} "
                                   f"({m.get('worst_reject_channel_share','')}% of rejections)"),
    ])

    # per-channel table
    ch_cols = []
    for key in m:
        if key.endswith("_exponent") and not key.startswith("AVERAGE"):
            ch_cols.append(key[:-len("_exponent")])
    ch_rows = ""
    for ch in ch_cols:
        ch_rows += ("<tr>"
                    f"<td class='k'>{html.escape(ch)}</td>"
                    f"<td>{m.get(f'{ch}_exponent','')}</td>"
                    f"<td>{m.get(f'{ch}_r2','')}</td>"
                    f"<td>{m.get(f'{ch}_logvar','')}</td>"
                    f"<td>{m.get(f'{ch}_total_reject_hits','')}</td>"
                    f"<td>{m.get(f'{ch}_pct_of_rejected_epochs','')}%</td>"
                    f"<td>{'yes' if m.get(f'{ch}_interpolated') else ''}</td>"
                    f"<td>{'yes' if m.get(f'{ch}_excluded') else ''}</td>"
                    "</tr>")

    doc = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>QC report - {html.escape(subject_id)}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:2rem auto;max-width:1000px;color:#1d3557;padding:0 1rem}}
h1{{font-size:1.5rem}} h2{{font-size:1.1rem;margin-top:1.6rem;border-bottom:2px solid #eee;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;margin:6px 0;font-size:.9rem}}
td{{border:1px solid #e6e6e6;padding:5px 8px}} td.k{{background:#f7f9fb;font-weight:600;width:34%}}
th{{background:#f0f4f8;border:1px solid #e6e6e6;padding:5px 8px;text-align:left;font-size:.85rem}}
.verdict{{padding:10px 14px;border-radius:8px;color:#fff;font-weight:600;background:{verdict_color}}}
.small{{color:#6b7c93;font-size:.8rem}}
</style></head><body>
<h1>Xon aperiodic QC report</h1>
<p class='small'>Subject <b>{html.escape(subject_id)}</b> &middot; auto-generated per recording. Everything below is derived from this single .xdf file.</p>
<p class='verdict'>{html.escape(verdict)}</p>
<h2>Identity</h2><table>{ident}</table>
<h2>Headline result</h2><table>{headline}</table>
<h2>Diagnostic figure</h2>{img_tag(diagnostic_path)}
<h2>How few minutes are enough?</h2>{img_tag(conv_img)}
<h2>Exponent over time (blocks)</h2>{img_tag(block_plot_path)}
<h2>Epoch quality control</h2><table>{qc_tbl}</table>
<h2>Preprocessing decisions</h2><table>{steps}</table>
<h2>Per-channel detail</h2>
<table><tr><th>channel</th><th>exponent</th><th>r^2</th><th>log-var</th><th>reject hits</th><th>% of rejections</th><th>interp?</th><th>excluded?</th></tr>{ch_rows}</table>
<p class='small'>Interpolated channels are reported but excluded from the AVERAGE exponent (a reconstructed channel is a blend of its neighbours, not an independent measurement).</p>
</body></html>"""
    out_path = os.path.join(output_dir, f"qc_report_{subject_id}.html")
    with open(out_path, "w") as fh:
        fh.write(doc)
    return out_path
