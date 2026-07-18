"""Assemble cohort statistics + figures into CSVs and a single HTML report a
researcher can read top-to-bottom (or hand to a mentor) and understand the study.
"""
from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from ..config import Config
from ..logging_utils import banner, info
from . import stats as S
from . import figures as F
from . import gallery as G


def _df_to_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p class='muted'>Not enough data for this analysis yet.</p>"
    return df.to_html(index=False, border=0, classes="tbl", na_rep="")


def _dict_to_html(d: Dict[str, Any]) -> str:
    if not d:
        return "<p class='muted'>Not available.</p>"
    rows = "".join(f"<tr><td class='k'>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
                   for k, v in d.items())
    return f"<table class='tbl'>{rows}</table>"


def _img(path: str, out_dir: Path) -> str:
    if not path:
        return ""
    rel = os.path.relpath(path, out_dir)     # e.g. figures/fig_x.png
    return (f"<figure><img src='{html.escape(rel)}' "
            "style='max-width:100%;border:1px solid #e6e6e6;border-radius:6px'></figure>")


def _interpretation(results_stats: Dict[str, Any]) -> str:
    """A few plain-English takeaways generated from the numbers."""
    bullets: List[str] = []
    rel = results_stats.get("reliability")
    if isinstance(rel, pd.DataFrame) and not rel.empty and "ICC(2,1)" in rel.columns:
        for _, r in rel.iterrows():
            icc = r.get("ICC(2,1)", "")
            if icc not in ("", None):
                bullets.append(f"Test-retest reliability for <b>{r['condition']}</b> is "
                               f"ICC(2,1) = {icc} ({r.get('note','')}), "
                               f"from {r.get('n_participants_complete')} participants.")
    con = results_stats.get("contrast", {})
    if con.get("n_pairs", 0) and "mean_diff_noisy_minus_quiet" in con:
        p = con.get("paired_t_p", con.get("wilcoxon_p", ""))
        bullets.append(f"{con['noisy']} vs {con['quiet']}: exponent differs by "
                       f"{con['mean_diff_noisy_minus_quiet']} on average "
                       f"(n={con['n_pairs']} pairs, p={p}).")
    rel = results_stats.get("duration_reliability", {}) or {}
    m_icc, m_sh = rel.get("minutes_for_good_icc", ""), rel.get("minutes_for_split_half", "")
    if m_sh not in ("", None) or m_icc not in ("", None):
        parts = []
        if m_sh not in ("", None):
            parts.append(f"internal-consistency (split-half) reliability reached "
                         f"{rel.get('split_half_target')} by <b>{m_sh} min</b>")
        if m_icc not in ("", None):
            parts.append(f"between-session reliability reached 'good' (ICC "
                         f"{rel.get('icc_target')}) by <b>{m_icc} min</b>")
        bullets.append("How few minutes are enough: " + "; ".join(parts) +
                       " of clean data — direct evidence for the 'a few minutes instead of "
                       "8 hours' premise.")
    q = results_stats.get("quality")
    if isinstance(q, pd.DataFrame) and not q.empty:
        r2 = q[(q["group"] == "all") & (q["metric"] == "fit r^2")]
        if not r2.empty:
            bullets.append(f"Across all recordings the mean fit r^2 was {r2.iloc[0]['mean']} "
                           "(higher = the 1/f slope genuinely fits the spectrum).")
    if not bullets:
        return "<p class='muted'>Interpretations will populate once a few complete recordings are processed.</p>"
    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"


def build_cohort_outputs(cfg: Config, master_df: pd.DataFrame, results: List[Any], out_dir: Path
                         ) -> Dict[str, str]:
    banner("COHORT STATISTICS & REPORT")
    out_dir = Path(out_dir)
    regions = cfg.section("stats").get("regions", {})
    quiet = cfg.get("stats", "quiet_condition", "rest")
    noisy = cfg.get("stats", "noisy_condition", "movie")
    sh_target = float(cfg.get("stats", "reliability_split_half_target", 0.90))
    icc_target = float(cfg.get("stats", "reliability_icc_target", 0.75))

    st = S.compute_all(master_df, results, regions, quiet, noisy, sh_target, icc_target)

    # organised sub-folders: figures/ and statistics/ (per_recording/ is written by the pipeline)
    fig_dir = out_dir / "figures"; fig_dir.mkdir(parents=True, exist_ok=True)
    stats_dir = out_dir / "statistics"; stats_dir.mkdir(parents=True, exist_ok=True)

    # write stat tables
    paths: Dict[str, str] = {}
    for name in ["quality", "reliability", "regional"]:
        df = st[name]
        if isinstance(df, pd.DataFrame) and not df.empty:
            p = stats_dir / f"stats_{name}.csv"
            df.to_csv(p, index=False)
            paths[f"stats_{name}"] = str(p)
    # reliability-vs-duration curve CSV
    rel = st.get("duration_reliability", {}) or {}
    rel_curve = rel.get("curve")
    if isinstance(rel_curve, pd.DataFrame) and not rel_curve.empty:
        p = stats_dir / "stats_reliability_by_duration.csv"
        rel_curve.to_csv(p, index=False)
        paths["stats_reliability_by_duration"] = str(p)

    # scalar summaries as a combined csv
    scalar = {}
    scalar.update({f"contrast.{k}": v for k, v in (st["contrast"] or {}).items()})
    scalar.update({f"regional_test.{k}": v for k, v in (st["regional_test"] or {}).items()})
    scalar.update({f"duration_reliability.{k}": v for k, v in rel.items() if k != "curve"})
    if scalar:
        p = stats_dir / "stats_summary.csv"
        pd.DataFrame([scalar]).to_csv(p, index=False)
        paths["stats_summary"] = str(p)

    figs = F.build_all(master_df, results, st["regional"], str(fig_dir), quiet, noisy, reliab=rel)
    paths.update({f"fig_{k}": v for k, v in figs.items()})

    # one-page gallery of every recording's diagnostic figure
    try:
        paths["gallery"] = G.build_gallery(out_dir, master_df)
        info(f"Diagnostics gallery: {paths['gallery']}")
    except Exception as exc:
        info(f"Gallery skipped ({exc}).")

    # cohort HTML report
    n_ok = int((master_df.get("status", pd.Series(dtype=str)).astype(str) != "error").sum()) if not master_df.empty else 0
    doc = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Xon aperiodic - cohort report</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:1050px;margin:2rem auto;color:#22333b;padding:0 1rem;line-height:1.5}}
h1{{font-size:1.7rem}} h2{{font-size:1.2rem;margin-top:2rem;border-bottom:2px solid #eee;padding-bottom:6px}}
.tbl{{border-collapse:collapse;width:100%;font-size:.86rem;margin:8px 0}}
.tbl td,.tbl th{{border:1px solid #e6e6e6;padding:5px 8px;text-align:left}}
.tbl th{{background:#f0f4f8}} td.k{{background:#f7f9fb;font-weight:600}}
.muted{{color:#8a94a6;font-style:italic}} figure{{margin:10px 0}}
.lead{{background:#eef4f8;border-left:4px solid #2a6f97;padding:10px 14px;border-radius:4px}}
</style></head><body>
<h1>Xon aperiodic pipeline &mdash; cohort report</h1>
<p class='lead'>Recordings processed: <b>{n_ok}</b>. This report answers the study's core
questions: can the Xon headset recover the aperiodic exponent accurately, is it reliable
across a person's repeat sessions, does it survive a noisy condition, and how few minutes
of clean data are needed.</p>

<h2>Key takeaways</h2>
{_interpretation(st)}

<h2>1. Measurement quality &amp; data yield</h2>
<p>Distribution of the exponent, fit r&sup2;, and how much clean data survived QC, overall and by condition.</p>
{_df_to_html(st['quality'])}
{_img(figs.get('quality',''), out_dir)}

<h2>2. Test-retest reliability (across a person's repeat sessions)</h2>
<p>ICC(2,1) is the standard test-retest statistic (&gt;0.75 good, &gt;0.9 excellent).</p>
{_df_to_html(st['reliability'])}
{_img(figs.get('test_retest',''), out_dir)}

<h2>3. Quiet vs noisy condition ({html.escape(str(quiet))} vs {html.escape(str(noisy))})</h2>
<p>Does the exponent hold up when the participant is watching a movie (more movement/noise)
versus resting? A paired contrast within each participant-session.</p>
{_dict_to_html(st['contrast'])}
{_img(figs.get('condition_paired',''), out_dir)}
{_img(figs.get('exponent_by_condition',''), out_dir)}

<h2>4. Scalp region</h2>
{_df_to_html(st['regional'])}
{_dict_to_html(st['regional_test'])}
{_img(figs.get('regional',''), out_dir)}

<h2>5. How few minutes are enough? (reliability vs recording length)</h2>
<p>We estimate the exponent using increasing amounts of clean data and ask how reliable it
becomes. Two standard measures: <b>split-half internal consistency</b> (odd vs even epochs,
Spearman-Brown corrected; target &ge; {sh_target}) and <b>between-session test-retest ICC</b>
(session&nbsp;1 vs session&nbsp;2; target &ge; {icc_target} = "good"). The shortest recording
length that reaches each target is the evidence-based answer to how few minutes are needed.</p>
{_dict_to_html({k: v for k, v in (st['duration_reliability'] or {}).items() if k != 'curve'})}
{_img(figs.get('reliability_by_duration',''), out_dir)}
{_img(figs.get('duration_overlay',''), out_dir)}
<p class='muted'>Method grounded in the aperiodic-reliability literature (McKeown et al. 2024,
Cerebral Cortex; epoch-increment split-half reliability as in EEG power-spectrum reliability
work). The full curve is in stats_reliability_by_duration.csv.</p>

<p class='muted'>See <b>gallery.html</b> for a one-page contact sheet of every recording's
diagnostic figure. Granular per-recording outputs are in <b>per_recording/</b>, figures in
<b>figures/</b>, statistics in <b>statistics/</b>.</p>

<h2>Methods &amp; references</h2>
<p style='font-size:.85rem;color:#33475b'>
Spectral parameterization (aperiodic exponent &amp; offset) via the FOOOF/specparam method:
<b>Donoghue et&nbsp;al. 2020</b>, <i>Parameterizing neural power spectra into periodic and
aperiodic components</i>, Nature Neuroscience 23:1655–1665.<br>
Acquisition &amp; artifact-rejection parameters (0.1&nbsp;Hz high-pass, 1&nbsp;s / 100&nbsp;ms
epochs, amplitude&nbsp;&gt;100&nbsp;µV or gradient&nbsp;&gt;10&nbsp;µV/ms rejection, ear/A2
reference) follow the Xon validation work of the <b>Boere &amp; Krigolson</b> lab
(Boere et&nbsp;al. 2025, Sci&nbsp;Rep; Boere, Copithorne &amp; Krigolson 2025, Exp&nbsp;Brain&nbsp;Res);
the gradient criterion reproduces Krigolson's published artifact-rejection routine.<br>
Reliability-vs-recording-length analysis (split-half internal consistency; between-session
test–retest ICC) follows <b>McKeown et&nbsp;al. 2024</b>, <i>Test–retest reliability of
spectral parameterization by 1/f characterization using SpecParam</i>, Cerebral&nbsp;Cortex
34:bhad482, and the epoch-increment reliability approach used in EEG power-spectrum
reliability studies. EMG contamination of high-frequency EEG: <b>Whitham et&nbsp;al. 2007</b>;
<b>Muthukumaraswamy 2013</b>. Preprocessing implemented with <b>MNE-Python</b>
(Gramfort et&nbsp;al. 2013). Full details in docs/METHODS.md.</p>
</body></html>"""
    report_path = out_dir / "cohort_report.html"
    with open(report_path, "w") as fh:
        fh.write(doc)
    paths["cohort_report"] = str(report_path)
    info(f"Cohort report: {report_path}")
    return paths
