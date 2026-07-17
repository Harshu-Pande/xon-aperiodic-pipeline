"""Publication-quality cohort figures. Clean, labelled, colour-blind-friendly, 300 dpi.

Each function guards on data availability and returns a path or None, so a small or
incomplete cohort simply produces fewer figures instead of crashing.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# A restrained publication style.
plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.labelsize": 12, "axes.grid": True,
    "grid.alpha": 0.25, "legend.frameon": False,
})
PALETTE = {"rest": "#2a6f97", "movie": "#e07a5f", "unknown": "#8d99ae"}
DPI = 300


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _ok(master: pd.DataFrame) -> pd.DataFrame:
    d = master.copy()
    if "status" in d.columns:
        d = d[d["status"].astype(str) != "error"]
    d["AVERAGE_exponent"] = _num(d.get("AVERAGE_exponent"))
    return d[d["AVERAGE_exponent"].notna()]


def _color(cond: str) -> str:
    return PALETTE.get(str(cond), "#8d99ae")


def exponent_by_condition(master: pd.DataFrame, out_dir: str) -> Optional[str]:
    d = _ok(master)
    if d.empty or "condition" not in d.columns:
        return None
    conds = [c for c in ["rest", "movie"] if c in set(d["condition"])]
    conds += [c for c in sorted(set(d["condition"])) if c not in conds]
    if not conds:
        return None
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, cond in enumerate(conds):
        vals = _num(d[d["condition"] == cond]["AVERAGE_exponent"]).dropna().values
        if len(vals) == 0:
            continue
        x = np.random.default_rng(0).normal(i, 0.06, size=len(vals))
        ax.scatter(x, vals, color=_color(cond), alpha=0.7, s=40, edgecolor="white", zorder=3)
        if len(vals) >= 2:
            ax.boxplot(vals, positions=[i], widths=0.5, showfliers=False,
                       medianprops=dict(color="black"))
    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels(conds)
    ax.set_ylabel("Aperiodic exponent (channel average)")
    ax.set_xlabel("Condition")
    ax.set_title("Aperiodic exponent by condition")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_exponent_by_condition.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def test_retest_scatter(master: pd.DataFrame, out_dir: str) -> Optional[str]:
    d = _ok(master)
    if d.empty or not {"participant", "session", "condition"}.issubset(d.columns):
        return None
    d = d[(d["participant"].astype(str).str.len() > 0) & (d["session"].astype(str).str.len() > 0)]
    conds = [c for c in sorted(set(d["condition"]))]
    plotted = False
    fig, ax = plt.subplots(figsize=(6, 6))
    for cond in conds:
        g = d[d["condition"] == cond]
        pivot = g.pivot_table(index="participant", columns="session",
                              values="AVERAGE_exponent", aggfunc="mean").dropna(axis=0, how="any")
        if pivot.shape[0] < 2 or pivot.shape[1] < 2:
            continue
        s = sorted(pivot.columns)[:2]
        a, b = pivot[s[0]].values, pivot[s[1]].values
        ax.scatter(a, b, color=_color(cond), s=55, alpha=0.8, edgecolor="white",
                   label=f"{cond} (n={len(a)})", zorder=3)
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
    hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
    ax.plot([lo, hi], [lo, hi], "--", color="gray", label="perfect agreement")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("Session 1 exponent")
    ax.set_ylabel("Session 2 exponent")
    ax.set_title("Test-retest: session 1 vs session 2")
    ax.legend()
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_test_retest.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def condition_paired(master: pd.DataFrame, out_dir: str, quiet: str = "rest", noisy: str = "movie") -> Optional[str]:
    d = _ok(master)
    if d.empty or not {"participant", "session", "condition"}.issubset(d.columns):
        return None
    d["key"] = d["participant"].astype(str) + "|" + d["session"].astype(str)
    q = d[d["condition"] == quiet].set_index("key")["AVERAGE_exponent"]
    n = d[d["condition"] == noisy].set_index("key")["AVERAGE_exponent"]
    common = sorted(set(q.index) & set(n.index))
    if len(common) < 2:
        return None
    fig, ax = plt.subplots(figsize=(6, 5))
    for k in common:
        ax.plot([0, 1], [float(q.loc[k]), float(n.loc[k])], "-", color="#adb5bd", alpha=0.7, zorder=1)
    ax.scatter([0] * len(common), [float(q.loc[k]) for k in common], color=_color(quiet),
               s=45, zorder=3, label=quiet)
    ax.scatter([1] * len(common), [float(n.loc[k]) for k in common], color=_color(noisy),
               s=45, zorder=3, label=noisy)
    ax.set_xticks([0, 1]); ax.set_xticklabels([f"{quiet}\n(quiet)", f"{noisy}\n(noisy)"])
    ax.set_ylabel("Aperiodic exponent")
    ax.set_title(f"Within-session: {quiet} vs {noisy} (n={len(common)} pairs)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_condition_paired.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def regional_bar(regional_df: pd.DataFrame, out_dir: str) -> Optional[str]:
    if regional_df is None or regional_df.empty:
        return None
    d = regional_df[_num(regional_df["n"]) > 0].copy()
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 5))
    means = _num(d["mean"]).values
    sds = _num(d["sd"]).fillna(0).values
    colors = ["#3d5a80", "#98c1d9", "#ee6c4d"][:len(d)]
    ax.bar(d["region"], means, yerr=sds, capsize=5, color=colors, edgecolor="black", alpha=0.9)
    ax.set_ylabel("Aperiodic exponent")
    ax.set_xlabel("Scalp region")
    ax.set_title("Aperiodic exponent by scalp region (mean +/- SD)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_regional.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def convergence_overlay(results: List[Any], out_dir: str) -> Optional[str]:
    """Overlay every recording's exponent-vs-minutes trajectory + the cohort median."""
    trajs = [(r.subject_id, r.convergence_df, getattr(r.metadata, "condition", "unknown"))
             for r in results if getattr(r, "convergence_df", None) is not None
             and not r.convergence_df.empty]
    if len(trajs) < 1:
        return None
    fig, ax = plt.subplots(figsize=(8, 5))
    all_curves = []
    for sid, df, cond in trajs:
        df = df.sort_values("clean_minutes")
        ax.plot(df["clean_minutes"], df["aperiodic_exponent"], color=_color(cond),
                alpha=0.35, linewidth=1.0)
        all_curves.append(df.set_index("clean_minutes")["aperiodic_exponent"])
    # cohort median on a common grid
    if len(all_curves) >= 2:
        grid = np.linspace(min(c.index.min() for c in all_curves),
                           min(c.index.max() for c in all_curves), 40)
        stacked = []
        for c in all_curves:
            stacked.append(np.interp(grid, c.index.values, c.values))
        med = np.median(np.array(stacked), axis=0)
        ax.plot(grid, med, color="black", linewidth=2.5, label="cohort median")
        ax.legend()
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Running aperiodic exponent")
    ax.set_title("Exponent stabilises with more clean data (all recordings)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_convergence_overlay.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def quality_scatter(master: pd.DataFrame, out_dir: str) -> Optional[str]:
    """Fit quality vs data retained - shows the headset gives good fits even with
    limited clean data (the whole point)."""
    d = _ok(master)
    if d.empty or "AVERAGE_r_squared" not in d.columns:
        return None
    d["r2"] = _num(d["AVERAGE_r_squared"])
    d["kept"] = _num(d.get("pct_epochs_kept"))
    d = d.dropna(subset=["r2"])
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 5))
    for cond, g in d.groupby("condition") if "condition" in d.columns else [("all", d)]:
        ax.scatter(g["kept"], g["r2"], color=_color(cond), s=45, alpha=0.8,
                   edgecolor="white", label=str(cond))
    ax.axhline(0.9, linestyle="--", color="gray", label="r^2 = 0.90")
    ax.set_xlabel("% epochs kept after QC")
    ax.set_ylabel("Average fit r^2")
    ax.set_title("Fit quality vs clean-data retention")
    ax.legend()
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_quality.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def build_all(master: pd.DataFrame, results: List[Any], regional_df: pd.DataFrame,
              out_dir: str, quiet: str = "rest", noisy: str = "movie") -> Dict[str, str]:
    figs: Dict[str, Optional[str]] = {
        "exponent_by_condition": exponent_by_condition(master, out_dir),
        "test_retest": test_retest_scatter(master, out_dir),
        "condition_paired": condition_paired(master, out_dir, quiet, noisy),
        "regional": regional_bar(regional_df, out_dir),
        "convergence_overlay": convergence_overlay(results, out_dir),
        "quality": quality_scatter(master, out_dir),
    }
    return {k: v for k, v in figs.items() if v}
