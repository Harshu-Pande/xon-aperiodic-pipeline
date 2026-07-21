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


def _regional_test_html(rt: dict) -> str:
    if not rt or rt.get("note"):
        return f"<p class='muted'>{html.escape(str(rt.get('note', 'unavailable')))}</p>"
    means = rt.get("region_means", {})
    head = (f"<p><b>Friedman</b> (n={rt.get('n_participants')} participants): "
            f"χ²={rt.get('statistic')}, p={rt.get('p_value')}. "
            f"Means: " + ", ".join(f"{k} {v}" for k, v in means.items()) + ".</p>")
    rows = "".join(
        f"<tr><td>{html.escape(ph['pair'])}</td><td>{ph['mean_diff']:+}</td>"
        f"<td>{ph['p_raw']}</td><td>{ph['p_holm']}</td>"
        f"<td>{'✓ significant' if ph['significant'] else 'ns'}</td></tr>"
        for ph in rt.get("posthoc", []))
    tbl = (f"<table class='tbl'><tr><th>pair</th><th>mean diff</th><th>p (raw)</th>"
           f"<th>p (Holm)</th><th></th></tr>{rows}</table>") if rows else ""
    return head + tbl


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
    min_n = int(cfg.get("stats", "reliability_min_n", 8))
    min_clean = float(cfg.get("stats", "min_clean_minutes", 0.0))
    region_cond = cfg.get("stats", "region_condition", "rest")
    demo_csv = cfg.get("stats", "demographics_csv", None)
    demo_path = str(cfg.resolve_path(demo_csv)) if demo_csv else None

    st = S.compute_all(master_df, results, regions, quiet, noisy, sh_target, icc_target,
                       min_n, min_clean, region_cond, demo_path)

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
    scalar.update({f"regional_test.{k}": v for k, v in (st["regional_test"] or {}).items()
                   if k not in ("posthoc", "region_means", "regions")})
    scalar.update({f"duration_reliability.{k}": v for k, v in rel.items() if k != "curve"})
    scalar.update({f"stabilization.{k}": v for k, v in (st.get("stabilization") or {}).items()})
    scalar.update({f"inclusion.{k}": v for k, v in (st.get("inclusion") or {}).items()})
    if scalar:
        p = stats_dir / "stats_summary.csv"
        pd.DataFrame([scalar]).to_csv(p, index=False)
        paths["stats_summary"] = str(p)

    figs = F.build_all(master_df, results, st["regional_pp"], st["regional_test"],
                       str(fig_dir), quiet, noisy, reliab=rel,
                       adj=st.get("adjacent_icc"), group_exp=st.get("group_exponent_duration"),
                       demo=st.get("demographics"))
    paths.update({f"fig_{k}": v for k, v in figs.items()})

    # one-page gallery of every recording's diagnostic figure
    try:
        paths["gallery"] = G.build_gallery(out_dir, master_df)
        info(f"Diagnostics gallery: {paths['gallery']}")
    except Exception as exc:
        info(f"Gallery skipped ({exc}).")

    # demographics section HTML (only if a CSV was provided and matched)
    demo = st.get("demographics", {}) or {}
    if demo.get("note"):
        demo_html = (f"<p class='muted'>Not shown — {html.escape(str(demo['note']))}. To enable, set "
                     "<code>stats.demographics_csv</code> to a CSV with columns participant, age, sex.</p>")
    else:
        bits = []
        if demo.get("age_pearson_r") is not None:
            bits.append(f"Exponent vs age: r = {demo['age_pearson_r']}, p = {demo['age_pearson_p']} "
                        f"(n = {demo.get('age_n')}).")
        if demo.get("sex_means"):
            sm = ", ".join(f"{k}: {v}" for k, v in demo["sex_means"].items())
            bits.append("Mean exponent by sex — " + sm +
                        (f"; Mann–Whitney p = {demo['sex_mannwhitney_p']}" if demo.get("sex_mannwhitney_p") is not None else ""))
        demo_html = ("<p>" + " ".join(bits) + f" (n = {demo.get('n')} participants)</p>"
                     + _img(figs.get("exponent_by_age", ""), out_dir)
                     + _img(figs.get("exponent_by_sex", ""), out_dir))

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
@media print {{ body{{max-width:none;margin:0.4in}} figure,table,ul{{page-break-inside:avoid}}
  h2{{page-break-after:avoid}} a[href]:after{{content:""}} }}
</style></head><body>
<h1>Xon aperiodic pipeline &mdash; cohort report</h1>
<p class='lead'>Recordings processed: <b>{n_ok}</b>. This is a <b>measurement-validation</b> report:
how <b>reliably and consistently</b> the Xon headset measures the aperiodic exponent —
across a person's repeat sessions, across a quiet vs noisy condition, by scalp region, and
with how few minutes of clean data. <b>Important:</b> without a simultaneous research-grade
reference recording, this assesses <b>reliability and consistency, not absolute accuracy</b>
(we cannot know the "true" exponent to compare against). See Limitations at the end.</p>

<p style='margin:14px 0'><a href='gallery.html' style='display:inline-block;background:#2a6f97;
color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600'>
&#128444; Open the diagnostics gallery &mdash; every recording on one page &rarr;</a></p>

<h2>Key takeaways</h2>
{_interpretation(st)}

<h2>1. Measurement quality &amp; data yield</h2>
<p>Distribution of the exponent, fit r&sup2;, and how much clean data survived QC, overall and by condition.</p>
{_df_to_html(st['quality'])}
{_img(figs.get('quality',''), out_dir)}

<h2>2. Test-retest reliability (across a person's repeat sessions)</h2>
<p>ICC(2,1) is the standard test-retest statistic (&gt;0.75 good, &gt;0.9 excellent), with a
bootstrap 95% CI. At this sample size the CIs are wide, so read them, not just the point
estimate. The scatter (identity line) and the Bland-Altman plot (bias &amp; 95% limits of
agreement) show the agreement directly.</p>
{_df_to_html(st['reliability'])}
{_img(figs.get('test_retest',''), out_dir)}
{_img(figs.get('bland_altman',''), out_dir)}

<h2>3. Quiet vs noisy condition ({html.escape(str(quiet))} vs {html.escape(str(noisy))})</h2>
<p>Two distinct questions, both of interest here:</p>
<p><b>(a) Does the exponent itself differ between the two states?</b> This is a real question
— the aperiodic exponent indexes excitation/inhibition balance, which can genuinely shift
between quiet rest and watching a movie, so a difference would be scientifically meaningful.
Paired within-participant contrast, with a 95% CI on the difference and Cohen's d<sub>z</sub>.
At this sample size it is underpowered, so <b>read the confidence interval</b> and treat a
non-significant result as "inconclusive," not "no difference."</p>
{_dict_to_html(st['contrast'])}
{_img(figs.get('condition_paired',''), out_dir)}
{_img(figs.get('exponent_by_condition',''), out_dir)}
<p><b>(b) Is the measurement robust to the noisy condition?</b> Separately from the value,
test-retest reliability and clean-data yield are better in rest than movie (section 2) — the
headset still works during the movie but with lower reliability and more rejected data.</p>

<h2>4. Scalp region (rest only)</h2>
<p>Uses <b>rest recordings only</b>, at the <b>participant level</b> — one value per person,
averaging that person's two rest sessions — to avoid pseudoreplication (pooling all
recordings would treat non-independent sessions/conditions as separate subjects and overstate
significance). Omnibus Friedman test plus Holm-corrected pairwise Wilcoxon signed-rank.</p>
{_regional_test_html(st['regional_test'])}
{_img(figs.get('regional',''), out_dir)}
<p class='muted'>Caveat: with 7 channels and the device ear (A2) reference, regional
differences are partly reference-dependent; treat the spatial pattern as suggestive and
confirm against a reference-robust montage before interpreting it as physiology.</p>

<h2>5. How few minutes are enough? (exponent &amp; reliability vs recording length)</h2>
<p>We recompute the exponent using increasing amounts of clean data (1&nbsp;min, 2&nbsp;min,
…) and ask two things:</p>
<p><b>(a) How does the exponent itself change, and when does it plateau?</b> The plot below
shows the <b>group-mean exponent</b> vs recording length (rest solid, movie dashed). It rises
over the first several minutes and then approaches an asymptote — the point past which more
data barely changes the group value.</p>
{_img(figs.get('group_exponent_by_duration',''), out_dir)}
<p><b>(b) When does the estimate stabilise / how reliable is it?</b> Two 0–1 curves:
<b>split-half internal consistency</b> (odd vs even epochs; target &ge; {sh_target}) stays
high throughout, and the <b>adjacent-minute ICC</b> — the agreement between the estimate at
one length and the next (1 vs 2 min, 2 vs 3 min …) — approaches 1 once adding a minute stops
changing the per-person estimate. The length where it settles is the data-driven "enough."</p>
{_img(figs.get('reliability_by_duration',''), out_dir)}
<p style='background:#eef4f8;border-left:4px solid #2a6f97;padding:8px 12px;border-radius:4px;font-size:.9rem'>
Adjacent-minute ICC stabilises by
<b>{(st.get('adjacent_icc') or {}).get('minutes_to_stable_icc','—')} min</b>; the group
exponent asymptote is visible in the plot above.</p>
<h3 style='font-size:1.05rem'>Every recording's curve (coloured by participant)</h3>
<p>Each recording's exponent as clean data accumulates — one colour per participant, rest
solid, movie dashed.</p>
{_img(figs.get('duration_overlay',''), out_dir)}
<h3 style='font-size:1.05rem'>Per-recording: when does each person's estimate settle?</h3>
<p>Each recording's duration-curve plot (in per_recording/) marks two <i>different</i> "how
much is enough" points, and the distinction matters:</p>
<ul style='font-size:.9rem'>
<li><b>Precise</b> (<code>minutes_to_stabilize</code>): where the two independent halves
(odd vs even epochs) agree — the estimate is <i>repeatable</i>. Usually reached quickly.</li>
<li><b>Reaches full value</b> (<code>minutes_to_converge</code>): where the running estimate
stops drifting toward the full-length value. <b>This is often much later</b> — short
recordings can give a <i>precise but biased</i> (typically too low) exponent that keeps
rising as more data is added.</li>
</ul>
<p style='background:#fff8e6;border-left:4px solid #e9a23b;padding:8px 12px;border-radius:4px;font-size:.9rem'>
<b>Why both matter:</b> a few minutes may give a <i>reliable</i> exponent, but not the
<i>same</i> value a long recording would — the short estimate can be systematically low.
For comparing people this bias may partly cancel if it is consistent; for absolute values it
does not. Worth confirming with the fixed vs knee fit and against a longer reference.</p>
{_dict_to_html(st.get('stabilization', {}))}
<p class='muted'>Method grounded in the aperiodic-reliability literature (McKeown et al. 2024,
Cerebral Cortex; epoch-increment split-half reliability as in EEG power-spectrum reliability
work). The full curve is in stats_reliability_by_duration.csv.</p>

<p class='muted'>See <b>gallery.html</b> for a one-page contact sheet of every recording's
diagnostic figure. Granular per-recording outputs are in <b>per_recording/</b>, figures in
<b>figures/</b>, statistics in <b>statistics/</b>.</p>

<h2>6. Demographics (age &amp; sex)</h2>
{demo_html}

<h2>Limitations &amp; how to read this</h2>
<ul style='font-size:.9rem;color:#33475b'>
<li><b>Reliability, not accuracy.</b> There is no simultaneous research-grade reference, so
we cannot verify the exponents are "correct" — only that they are reproducible. Concurrent
recording against a validated system would be needed to claim accuracy.</li>
<li><b>Small sample.</b> Reliability and group tests rest on ~10 participants; confidence
intervals are wide and null results (e.g. rest vs movie value) are underpowered — absence of
a difference is not evidence of no difference.</li>
<li><b>Independence.</b> Each person contributes multiple recordings; group tests here are
computed per participant to avoid pseudoreplication. Pooled descriptive tables mix
sessions/conditions and should not be read as independent samples.</li>
<li><b>Reference dependence.</b> At 7 channels, regional and average-referenced results shift
with the reference choice; spatial patterns are suggestive, not definitive.</li>
<li><b>Data yield.</b> A few sessions retain very little clean data after rejection and are
low-confidence; a minimum clean-duration inclusion rule is worth pre-registering.</li>
<li><b>Fit model.</b> A fixed (no-knee) 1/f fit over 1–40 Hz is used; a knee-mode
sensitivity check is advisable where fits are poorer.</li>
</ul>

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

    # share-ready exports: figures.pdf, single-file standalone HTMLs, and a bundle .zip
    try:
        from . import export as EX
        paths.update(EX.export_all(out_dir))
        info("Share formats written: figures.pdf, *_standalone.html, and a results bundle .zip.")
    except Exception as exc:  # noqa: BLE001
        info(f"Export step skipped ({exc}).")
    return paths
