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


def regional_bar(pp_df, regional_test: dict, out_dir: str) -> Optional[str]:
    """Participant-level regional exponents: each participant's three regions connected,
    group means overlaid, and the omnibus + significant post-hoc p-values annotated."""
    if pp_df is None or len(pp_df) == 0:
        return None
    regions = [r for r in ["frontal", "central", "parietal"] if r in pp_df.columns]
    if len(regions) < 2:
        return None
    x = list(range(len(regions)))
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    # per-participant lines (shows the within-subject pattern honestly)
    for _, row in pp_df.iterrows():
        ax.plot(x, [row[r] for r in regions], color="#adb5bd", alpha=0.6, marker="o",
                markersize=4, linewidth=1, zorder=1)
    means = [float(pp_df[r].mean()) for r in regions]
    sems = [float(pp_df[r].std(ddof=1) / np.sqrt(len(pp_df))) for r in regions]
    ax.errorbar(x, means, yerr=sems, color="#264653", marker="s", markersize=10,
                linewidth=2.5, capsize=6, zorder=3, label="mean ± SEM")
    ax.set_xticks(x); ax.set_xticklabels(regions)
    ax.set_ylabel("Aperiodic exponent")
    ax.set_xlabel("Scalp region")
    n = regional_test.get("n_participants", len(pp_df))
    ax.set_title(f"Aperiodic exponent by scalp region (n={n} participants)")
    # annotate omnibus + significant post-hoc
    lines = []
    if regional_test.get("p_value") not in (None, ""):
        lines.append(f"Friedman: χ²={regional_test.get('statistic')}, p={regional_test.get('p_value')}")
    for ph in regional_test.get("posthoc", []):
        if ph.get("significant"):
            lines.append(f"{ph['pair']}: p(Holm)={ph['p_holm']} *")
    if lines:
        ax.text(0.02, 0.98, "\n".join(lines), transform=ax.transAxes, va="top", ha="left",
                fontsize=9, bbox=dict(boxstyle="round", facecolor="#fff8e6", edgecolor="#e9a23b"))
    ax.legend(loc="lower left")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_regional.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def duration_overlay(results: List[Any], out_dir: str) -> Optional[str]:
    """Overlay every recording's exponent-vs-minutes curve + the cohort median."""
    trajs = [(r.subject_id, r.duration_df, getattr(r.metadata, "condition", "unknown"))
             for r in results if getattr(r, "duration_df", None) is not None
             and not r.duration_df.empty]
    if len(trajs) < 1:
        return None
    fig, ax = plt.subplots(figsize=(8, 5))
    all_curves = []
    for sid, df, cond in trajs:
        df = df.sort_values("clean_minutes")
        ax.plot(df["clean_minutes"], _num(df["exponent_all"]), color=_color(cond),
                alpha=0.35, linewidth=1.0)
        all_curves.append(df.set_index("clean_minutes")["exponent_all"])
    if len(all_curves) >= 2:
        grid = np.linspace(min(c.index.min() for c in all_curves),
                           min(c.index.max() for c in all_curves), 40)
        stacked = [np.interp(grid, c.index.values, pd.to_numeric(c.values, errors="coerce"))
                   for c in all_curves]
        med = np.median(np.array(stacked), axis=0)
        ax.plot(grid, med, color="black", linewidth=2.5, label="cohort median")
        ax.legend()
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Aperiodic exponent")
    ax.set_title("Exponent estimate vs recording length (all recordings)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_duration_overlay.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def reliability_curve(reliab: dict, out_dir: str) -> Optional[str]:
    """Split-half internal consistency and between-session ICC vs recording length.

    Only the region where enough recordings contribute is drawn: past a certain length
    only a handful of recordings are long enough (and test-retest needs a matched pair of
    sessions), so the estimate there is noise, not signal. Plotting it would misleadingly
    suggest reliability collapses with more data, when it is just a shrinking sample.
    """
    curve = reliab.get("curve")
    if curve is None or len(curve) == 0:
        return None
    min_n = int(reliab.get("min_n", 8))
    m = pd.to_numeric(curve["minutes"], errors="coerce")
    sh = pd.to_numeric(curve["split_half_reliability"], errors="coerce")
    icc = pd.to_numeric(curve["test_retest_icc"], errors="coerce")
    n_sh = pd.to_numeric(curve["n_split_half"], errors="coerce")
    n_icc = pd.to_numeric(curve["n_icc"], errors="coerce")
    sh_ok = sh.notna() & (n_sh >= min_n)     # only trustworthy points
    icc_ok = icc.notna() & (n_icc >= min_n)
    if not (sh_ok.any() or icc_ok.any()):
        return None
    sh_t = reliab.get("split_half_target", 0.90)
    icc_t = reliab.get("icc_target", 0.75)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    if sh_ok.any():
        ax.plot(m[sh_ok], sh[sh_ok], marker="o", color="#2a6f97", label="split-half (odd vs even)")
        ax.axhline(sh_t, color="#2a6f97", linestyle=":", alpha=0.7)
    if icc_ok.any():
        ax.plot(m[icc_ok], icc[icc_ok], marker="s", color="#e07a5f",
                label="test-retest ICC (session 1 vs 2)")
        ax.axhline(icc_t, color="#e07a5f", linestyle=":", alpha=0.7)
    for key, color in [("minutes_for_split_half", "#2a6f97"), ("minutes_for_good_icc", "#e07a5f")]:
        v = reliab.get(key, "")
        if v not in ("", None):
            ax.axvline(float(v), color=color, linestyle="--", alpha=0.6)
    # x-limit to the trustworthy region (a little headroom)
    max_min = reliab.get("max_trustworthy_minutes", "")
    if max_min not in ("", None):
        ax.set_xlim(0, float(max_min) * 1.05)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Reliability")
    ax.set_title("Reliability of the aperiodic exponent vs recording length")
    ax.text(0.5, 1.015, f"shown only where ≥ {min_n} recordings contribute",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=9, color="#6b7c93")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_reliability_by_duration.png")
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


def bland_altman(master: pd.DataFrame, out_dir: str) -> Optional[str]:
    """Bland-Altman agreement of session 1 vs session 2 (per condition): difference vs
    mean, with the mean bias and 95% limits of agreement — the standard test-retest plot."""
    d = _ok(master)
    if d.empty or not {"participant", "session", "condition"}.issubset(d.columns):
        return None
    conds = [c for c in sorted(set(d["condition"])) if c in ("rest", "movie")] or sorted(set(d["condition"]))
    panels = []
    for cond in conds:
        g = d[d["condition"] == cond]
        piv = g.pivot_table(index="participant", columns="session", values="AVERAGE_exponent",
                            aggfunc="mean").dropna(axis=0, how="any")
        if piv.shape[0] >= 3 and piv.shape[1] >= 2:
            s = sorted(piv.columns)[:2]
            panels.append((cond, piv[s[0]].values, piv[s[1]].values))
    if not panels:
        return None
    fig, axes = plt.subplots(1, len(panels), figsize=(5.5 * len(panels), 5), squeeze=False)
    for ax, (cond, a, b) in zip(axes[0], panels):
        mean = (a + b) / 2; diff = a - b
        bias = float(np.mean(diff)); sd = float(np.std(diff, ddof=1))
        ax.scatter(mean, diff, color=_color(cond), s=55, alpha=0.8, edgecolor="white", zorder=3)
        ax.axhline(bias, color="#264653", linestyle="-", label=f"bias {bias:+.3f}")
        ax.axhline(bias + 1.96 * sd, color="#e63946", linestyle="--",
                   label=f"95% LoA ±{1.96*sd:.3f}")
        ax.axhline(bias - 1.96 * sd, color="#e63946", linestyle="--")
        ax.axhline(0, color="gray", linewidth=0.6)
        ax.set_title(f"{cond} (n={len(a)})")
        ax.set_xlabel("Mean of the two sessions")
        ax.set_ylabel("Session 1 − Session 2")
        ax.legend(fontsize=8)
    fig.suptitle("Test–retest agreement (Bland–Altman)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_bland_altman.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def build_all(master: pd.DataFrame, results: List[Any], regional_pp, regional_test: dict,
              out_dir: str, quiet: str = "rest", noisy: str = "movie",
              reliab: Optional[dict] = None) -> Dict[str, str]:
    figs: Dict[str, Optional[str]] = {
        "exponent_by_condition": exponent_by_condition(master, out_dir),
        "test_retest": test_retest_scatter(master, out_dir),
        "bland_altman": bland_altman(master, out_dir),
        "condition_paired": condition_paired(master, out_dir, quiet, noisy),
        "regional": regional_bar(regional_pp, regional_test or {}, out_dir),
        "reliability_by_duration": reliability_curve(reliab or {}, out_dir),
        "duration_overlay": duration_overlay(results, out_dir),
        "quality": quality_scatter(master, out_dir),
    }
    return {k: v for k, v in figs.items() if v}
