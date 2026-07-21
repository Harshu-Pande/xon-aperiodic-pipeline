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
    cond = regional_test.get("condition", "rest")
    ax.set_title(f"Aperiodic exponent by scalp region (n={n} participants, {cond} only, sessions averaged)")
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
    """Each recording's exponent-vs-minutes curve, coloured by PARTICIPANT; rest = solid,
    movie = dashed. No cohort summary line."""
    from matplotlib.lines import Line2D
    trajs = [(r.subject_id, r.duration_df, getattr(r.metadata, "participant", ""),
              getattr(r.metadata, "condition", "unknown"))
             for r in results if getattr(r, "duration_df", None) is not None
             and not r.duration_df.empty]
    if not trajs:
        return None
    participants = sorted({p for _, _, p, _ in trajs if p})
    cmap = plt.get_cmap("tab20" if len(participants) > 10 else "tab10")
    pcolor = {p: cmap(i % cmap.N) for i, p in enumerate(participants)}
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for sid, df, part, cond in trajs:
        df = df.sort_values("clean_minutes")
        style = "--" if str(cond) == "movie" else "-"
        ax.plot(df["clean_minutes"], _num(df["exponent_all"]),
                color=pcolor.get(part, "#888888"), linestyle=style, alpha=0.85, linewidth=1.3)
    part_handles = [Line2D([0], [0], color=pcolor[p], lw=2, label=p) for p in participants]
    style_handles = [Line2D([0], [0], color="#555555", lw=2, linestyle="-", label="rest"),
                     Line2D([0], [0], color="#555555", lw=2, linestyle="--", label="movie")]
    leg1 = ax.legend(handles=part_handles, title="participant", fontsize=7,
                     ncol=2, loc="lower right")
    ax.add_artist(leg1)
    ax.legend(handles=style_handles, loc="upper left", fontsize=9)
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Aperiodic exponent")
    ax.set_title("Exponent vs recording length — per recording (colour = participant)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_duration_overlay.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def reliability_curve(reliab: dict, adj: dict, out_dir: str) -> Optional[str]:
    """Two reliability curves vs recording length, both on a 0–1 scale:
      * split-half internal consistency (odd vs even epochs) — kept;
      * adjacent-minute ICC (1 vs 2 min, 2 vs 3 min …) — how fast the per-recording estimate
        stops changing as data accumulates (replaces the between-session test-retest line).
    """
    curve = (reliab or {}).get("curve")
    adj_curve = (adj or {}).get("curve")
    have_sh = curve is not None and len(curve) > 0
    have_adj = adj_curve is not None and len(adj_curve) > 0
    if not have_sh and not have_adj:
        return None
    fig, ax = plt.subplots(figsize=(8.5, 5))
    if have_sh:
        min_n = int(reliab.get("min_n", 8))
        m = pd.to_numeric(curve["minutes"], errors="coerce")
        sh = pd.to_numeric(curve["split_half_reliability"], errors="coerce")
        n_sh = pd.to_numeric(curve["n_split_half"], errors="coerce")
        ok = sh.notna() & (n_sh >= min_n)
        if ok.any():
            ax.plot(m[ok], sh[ok], marker="o", color="#2a6f97", label="split-half (odd vs even)")
            ax.axhline(reliab.get("split_half_target", 0.90), color="#2a6f97", linestyle=":", alpha=0.6)
    if have_adj:
        am = pd.to_numeric(adj_curve["minutes"], errors="coerce")
        ai = pd.to_numeric(adj_curve["icc"], errors="coerce")
        ok = ai.notna()
        if ok.any():
            ax.plot(am[ok], ai[ok], marker="s", color="#e07a5f",
                    label="adjacent-minute ICC (1v2, 2v3, …)")
        ax.axhline(adj.get("icc_target", 0.75), color="#e07a5f", linestyle=":", alpha=0.6)
        v = adj.get("minutes_to_stable_icc", "")
        if v not in ("", None):
            ax.axvline(float(v), color="#e07a5f", linestyle="--", alpha=0.6,
                       label=f"estimate stable by {float(v):.0f} min")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Reliability")
    ax.set_title("Reliability of the aperiodic exponent vs recording length")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_reliability_by_duration.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def group_exponent_curve(group_exp: dict, out_dir: str) -> Optional[str]:
    """Group-mean aperiodic exponent (± SEM) vs cumulative recording length, by condition
    (rest solid, movie dashed). Shows how the group exponent rises and approaches an
    asymptote as more clean data is used."""
    if not group_exp:
        return None
    bycond = group_exp.get("by_condition", {}) or {}
    fig, ax = plt.subplots(figsize=(8.5, 5))
    plotted = False
    for cond, style in [("rest", "-"), ("movie", "--")]:
        df = bycond.get(cond)
        if df is None or len(df) == 0:
            continue
        m = pd.to_numeric(df["minutes"], errors="coerce")
        mean = pd.to_numeric(df["mean"], errors="coerce")
        sem = pd.to_numeric(df["sem"], errors="coerce").fillna(0)
        ax.plot(m, mean, style, color=_color(cond), linewidth=2.2, label=f"{cond} (mean ± SEM)")
        ax.fill_between(m, mean - sem, mean + sem, color=_color(cond), alpha=0.15)
        plotted = True
    ov = group_exp.get("overall")
    if ov is not None and len(ov):
        ax.plot(pd.to_numeric(ov["minutes"], errors="coerce"),
                pd.to_numeric(ov["mean"], errors="coerce"),
                color="#333333", linewidth=1.0, alpha=0.5, label="all recordings")
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    ax.set_xlabel("Clean data used (minutes)")
    ax.set_ylabel("Aperiodic exponent (group mean)")
    ax.set_title("How the group exponent changes with recording length")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_group_exponent_by_duration.png")
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
        ax.set_xlabel("Mean aperiodic exponent (sessions 1 & 2)")
        ax.set_ylabel("Exponent difference (session 1 − session 2)")
        ax.legend(fontsize=8)
    fig.suptitle("Test–retest agreement of the aperiodic exponent (Bland–Altman)")
    fig.tight_layout()
    p = os.path.join(out_dir, "fig_bland_altman.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p


def exponent_by_age(demo: dict, out_dir: str) -> Optional[str]:
    t = (demo or {}).get("table")
    if t is None or "age" not in getattr(t, "columns", []):
        return None
    d = t.copy(); d["age"] = _num(d["age"]); d["e"] = _num(d["AVERAGE_exponent"])
    d = d.dropna(subset=["age", "e"])
    if len(d) < 3:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(d["age"], d["e"], s=60, color="#2a6f97", edgecolor="white", zorder=3)
    try:
        z = np.polyfit(d["age"].values, d["e"].values, 1)
        xs = np.linspace(d["age"].min(), d["age"].max(), 50)
        ax.plot(xs, z[0] * xs + z[1], "--", color="#e07a5f")
    except Exception:
        pass
    r, p = demo.get("age_pearson_r"), demo.get("age_pearson_p")
    title = "Aperiodic exponent vs age"
    if r is not None:
        title += f"  (r={r}, p={p}, n={demo.get('age_n')})"
    ax.set_title(title); ax.set_xlabel("Age (years)")
    ax.set_ylabel("Aperiodic exponent (per participant)")
    ax.grid(True, alpha=0.25); fig.tight_layout()
    p_ = os.path.join(out_dir, "fig_exponent_by_age.png")
    fig.savefig(p_, bbox_inches="tight"); plt.close(fig)
    return p_


def exponent_by_sex(demo: dict, out_dir: str) -> Optional[str]:
    t = (demo or {}).get("table")
    if t is None or "sex" not in getattr(t, "columns", []):
        return None
    groups = {str(s): _num(g["AVERAGE_exponent"]).dropna().values
              for s, g in t.groupby("sex") if str(s).strip()}
    groups = {k: v for k, v in groups.items() if len(v) >= 1}
    if len(groups) < 2:
        return None
    fig, ax = plt.subplots(figsize=(6, 5))
    rng = np.random.default_rng(0)
    for i, (s, y) in enumerate(groups.items()):
        ax.scatter(rng.normal(i, 0.05, len(y)), y, s=55, alpha=0.8, edgecolor="white", zorder=3)
        if len(y) >= 2:
            ax.boxplot(y, positions=[i], widths=0.5, showfliers=False)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(list(groups.keys()))
    p = demo.get("sex_mannwhitney_p")
    ax.set_title("Aperiodic exponent by sex" + (f"  (Mann–Whitney p={p})" if p is not None else ""))
    ax.set_ylabel("Aperiodic exponent (per participant)"); ax.set_xlabel("Sex")
    ax.grid(True, alpha=0.25, axis="y"); fig.tight_layout()
    p_ = os.path.join(out_dir, "fig_exponent_by_sex.png")
    fig.savefig(p_, bbox_inches="tight"); plt.close(fig)
    return p_


def build_all(master: pd.DataFrame, results: List[Any], regional_pp, regional_test: dict,
              out_dir: str, quiet: str = "rest", noisy: str = "movie",
              reliab: Optional[dict] = None, adj: Optional[dict] = None,
              group_exp: Optional[dict] = None, demo: Optional[dict] = None) -> Dict[str, str]:
    figs: Dict[str, Optional[str]] = {
        "exponent_by_condition": exponent_by_condition(master, out_dir),
        "test_retest": test_retest_scatter(master, out_dir),
        "bland_altman": bland_altman(master, out_dir),
        "condition_paired": condition_paired(master, out_dir, quiet, noisy),
        "regional": regional_bar(regional_pp, regional_test or {}, out_dir),
        "reliability_by_duration": reliability_curve(reliab or {}, adj or {}, out_dir),
        "group_exponent_by_duration": group_exponent_curve(group_exp or {}, out_dir),
        "duration_overlay": duration_overlay(results, out_dir),
        "quality": quality_scatter(master, out_dir),
        "exponent_by_age": exponent_by_age(demo or {}, out_dir),
        "exponent_by_sex": exponent_by_sex(demo or {}, out_dir),
    }
    return {k: v for k, v in figs.items() if v}
