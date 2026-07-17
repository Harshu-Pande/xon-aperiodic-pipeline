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
    return (f"<figure><img src='{html.escape(os.path.basename(path))}' "
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
    conv = results_stats.get("convergence", {})
    if conv.get("n_converged"):
        med = conv.get("minutes_to_stability_median", "")
        bullets.append(f"{conv.get('pct_converged')}% of recordings reached a stable exponent; "
                       f"median time to stability was {med} minutes of clean data - central to the "
                       "'a few minutes instead of 8 hours' goal.")
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

    st = S.compute_all(master_df, regions, quiet, noisy)

    # write stat tables
    paths: Dict[str, str] = {}
    for name in ["quality", "reliability", "regional"]:
        df = st[name]
        if isinstance(df, pd.DataFrame) and not df.empty:
            p = out_dir / f"stats_{name}.csv"
            df.to_csv(p, index=False)
            paths[f"stats_{name}"] = str(p)
    # scalar summaries as a combined csv
    scalar = {}
    scalar.update({f"contrast.{k}": v for k, v in (st["contrast"] or {}).items()})
    scalar.update({f"regional_test.{k}": v for k, v in (st["regional_test"] or {}).items()})
    scalar.update({f"convergence.{k}": v for k, v in (st["convergence"] or {}).items()})
    if scalar:
        p = out_dir / "stats_summary.csv"
        pd.DataFrame([scalar]).to_csv(p, index=False)
        paths["stats_summary"] = str(p)

    figs = F.build_all(master_df, results, st["regional"], str(out_dir), quiet, noisy)
    paths.update({f"fig_{k}": v for k, v in figs.items()})

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

<h2>5. How few minutes are enough? (convergence)</h2>
<p>For each recording we track the running exponent as clean data accumulates and record
when it settles within tolerance of the full-recording value.</p>
{_dict_to_html(st['convergence'])}
{_img(figs.get('convergence_overlay',''), out_dir)}

<p class='muted'>Per-recording QC reports (qc_report_&lt;id&gt;.html) and the wide
master_everything.csv sit alongside this file for drill-down.</p>
</body></html>"""
    report_path = out_dir / "cohort_report.html"
    with open(report_path, "w") as fh:
        fh.write(doc)
    paths["cohort_report"] = str(report_path)
    info(f"Cohort report: {report_path}")
    return paths
