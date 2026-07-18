# Critical review of the analysis (real cohort, n = 10 participants / 39 recordings)

A candid assessment of *what we are measuring, what we can claim, and whether the analyses
and figures are the right ones*. Numbers below are from the real run.

## 1. The single most important reframing: reliability, not accuracy

The study cannot currently claim the headset measures the exponent **accurately**, because
there is no simultaneous research-grade reference recording to compare against — we never
observe the "true" exponent. What the data *can* support is **reliability and consistency**
(does the same person give the same number again; do internal splits agree). The report and
figures have been reworded accordingly. **To claim accuracy you need a concurrent recording
against a validated system** on the same subjects; that is the highest-value next experiment.

## 2. Reliability — read the confidence intervals, not the point estimates

Test–retest ICC(2,1), session 1 vs session 2, with bootstrap 95% CIs:

| Condition | ICC | 95% CI | Interpretation |
|---|---|---|---|
| **rest** | 0.90 | **[0.72, 0.98]** | good–excellent, and solid |
| **movie** | 0.58 | **[0.02, 0.79]** | essentially *uncertain* at this n |

The rest result is genuinely good. The movie CI spans 0.02–0.79 — from "no reliability" to
"good" — so at n = 9 we effectively **cannot conclude anything about movie reliability**. The
old figure/point-estimate hid this. Sensitivity check: dropping the heavily-rejected outlier
P002 barely moves either (rest 0.90→0.87, movie 0.58→0.58), so the movie problem is systemic
(it's a noisier condition), not one bad participant.

**Added:** bootstrap CIs and Bland–Altman agreement plots (bias + 95% limits of agreement),
which are the standard way to show test–retest agreement.

## 3. Rest vs movie — two questions, both worth reporting

There are two distinct comparisons here and both matter:

**(a) Does the exponent value differ between states?** This is a real scientific question —
the exponent indexes E/I balance, which can shift between rest and watching a movie. On the
real data: mean diff = −0.026, **95% CI [−0.094, +0.043]**, Cohen's d_z = −0.18, p = 0.44.
The honest reading is not "no difference" but "**no evidence of a difference, and only
powered to detect a moderate-to-large one**" — the CI rules out a large shift but is
compatible with a small one either way. Reported with a CI + effect size (added), not just a
p-value.

**(b) Is the measurement robust to the noisy condition?** Separately, reliability and yield
are better in rest (ICC 0.90 vs 0.58; ~77% vs 69% epochs retained). So the headset works in
both, but the noisy condition is measured less reliably.

Both are now in the report as distinct points — the value contrast is a substantive result,
not a footnote.

## 4. Regional analysis — pseudoreplication fixed, and the real result is smaller

The original regional Friedman treated all 34 recordings as independent subjects, but they
are 2 sessions × 2 conditions from 10 people. Recomputed correctly **at the participant
level**:

- Omnibus Friedman: χ² = 7.4, **p = 0.025** (was reported ≈ 0.000 when pseudoreplicated).
- Post-hoc (Holm-corrected Wilcoxon): **central > parietal, p = 0.006** (the one robust
  effect); frontal > parietal p = 0.055 (marginal); frontal vs central p = 0.28 (ns).

So the honest statement is "**a posterior gradient — parietal lower than central**," not the
clean "frontal > central > parietal" the old bar chart implied. **Added:** participant-level
computation, post-hoc pairwise tests, individual-participant lines on the figure, and the
p-values annotated on the plot (your specific request). **Caveat:** at 7 channels with the
ear (A2) reference, regional differences shift with the reference choice, so treat the
spatial pattern as suggestive until confirmed under a reference-robust setup.

## 5. What we *should* be comparing (for a validation study)

Ranked by value:

1. **Test–retest reliability** per condition (have it, now with CIs + Bland–Altman). Primary.
2. **Minimum recording length** for adequate reliability (have it; ~1–2 min reaches the
   targets). Directly supports the "few minutes" thesis.
3. **Robustness to the noisy condition** — expressed as reliability/quality (rest vs movie),
   not the exponent value.
4. **Agreement with a gold standard** — *missing and most important for "accuracy."* Needs a
   concurrent validated recording.
5. **Regional structure vs the published topography** — a sanity check that the device
   reproduces known spatial patterns, not a novel finding.
6. **Sensitivity analyses** — knee vs fixed FOOOF fit, reference choice, inclusion threshold.

Things **not** worth over-interpreting: absolute exponent values (no ground truth); any
group difference at n = 10 (underpowered); pooled descriptive stats as if independent.

## 6. Data-quality / inclusion

A few sessions retain very little clean data (P002 movie: 4.0 and 6.7 clean min, ~80–88%
rejected; P009 S2 rest: 6.75 min). These are low-confidence. A **pre-registered minimum
clean-duration** (e.g. ≥ 5 min) is advisable; a `stats.min_clean_minutes` setting now
supports this, and the report records what was excluded. We showed rest reliability is robust
to excluding the worst offender, which is reassuring.

## 7. Concrete recommendations

- **For accuracy:** run a concurrent-recording validation against a research EEG system.
- **Pre-register:** the inclusion rule (min clean minutes), the primary endpoint
  (test–retest ICC in rest), and the fit settings, before the confirmatory cohort.
- **Report CIs everywhere** and avoid drawing conclusions from point estimates at this n.
- **Run the built-in sensitivity toggles** (knee mode; reference = average vs ear) and report
  whether conclusions hold.
- **Grow the sample** — 10 participants is a pilot; the movie CI shows why.

## What changed in the code as a result

Participant-level regional test + Holm post-hoc + p-values on the figure; bootstrap ICC CIs;
Bland–Altman plots; the rest-vs-movie value contrast reported with a 95% CI + effect size (as
a substantive result); a **per-recording stabilization** metric (`minutes_to_stabilize`) — the
length at which a recording's two independent halves agree, i.e. how much data is enough for
that individual — annotated on each recording's duration-curve plot and summarised for the
cohort; reframing of accuracy→reliability; an optional minimum-clean-duration inclusion rule;
and a Limitations section in the report.
