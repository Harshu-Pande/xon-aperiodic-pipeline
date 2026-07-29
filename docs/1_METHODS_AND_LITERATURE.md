# 1 — Methods & the literature behind them

*Why each setting is what it is, and the paper it comes from. Every default in
`config/config.yaml` should be traceable to a row in this document.*

---

## 1.1 The measure: aperiodic exponent

The EEG power spectrum is the sum of **rhythmic peaks** (alpha, beta …) sitting on a
**broadband 1/f-like background**. The background's slope on log-log axes is the
**aperiodic exponent**.

- **Method:** FOOOF / specparam — Donoghue et al. (2020), *Parameterizing neural power
  spectra into periodic and aperiodic components*, **Nature Neuroscience** 23:1655–1665.
- **Why it matters for AD:** a flatter slope (lower exponent) is interpreted as a shift
  toward **excitation** in excitation–inhibition (E/I) balance. AD disrupts E/I balance in
  ways tied to amyloid and tau.
- **Honest caveat we keep in the report:** the exponent→E/I link is a *putative* marker
  from modelling and pharmacology work, and is debated. Aperiodic changes in preclinical /
  prodromal AD are also **region-dependent** (flattening in some regions, steepening in
  others), so direction is not a simple one-way shift.
- **Aging confound:** the exponent flattens with normal aging (Voytek et al. 2015), so an
  AD-vs-control design must be age-matched.

---

## 1.2 Acquisition & preprocessing settings

The Xon-specific parameters follow the **Boere & Krigolson** lab's Xon validation work
(Boere et al. 2025, *Sci Rep*; Boere, Copithorne & Krigolson 2025, *Exp Brain Res*).

| Setting | Value | Where it comes from |
|---|---|---|
| `filter.high_pass_hz` | **0.1 Hz** | Krigolson/Boere Xon protocol; removes drift without distorting the low-frequency slope. A higher high-pass (1 Hz) would bite into the 1–40 Hz fit band. |
| `filter.notch_freq_hz` | **60 Hz** (+ harmonics) | North-American mains. The notch and its harmonics are applied up to Nyquist. Set to `50` outside NA. |
| `epoch.length_sec` | **1.0 s** | Krigolson artifact-rejection routine. Also gives 1 Hz spectral resolution, matching the fit band's lower edge. |
| `epoch.overlap_sec` | **0.1 s** | Same protocol; mild overlap stabilises the Welch average. |
| `artifacts.amplitude_threshold_uv` | **100 µV** peak-to-peak | Krigolson routine. |
| `artifacts.gradient_threshold_uv_per_ms` | **10 µV/ms** | Reproduces Krigolson's *Gradient* step. At 250 Hz a 40 µV sample-to-sample step == 10 µV/ms. |
| `artifacts.flat_threshold_uv` | **1 µV** | Dead/disconnected electrode detection. |
| `montage.name` | **standard_1020** | Gives the 7 Xon electrodes real scalp positions, needed for interpolation and regional grouping. |
| `artifacts.reference` | **null** = device ear-clip (A2) | The Xon's native reference. Changing it changes absolute exponent values, so it is held constant across the study. |
| `xdf.data_units` | **uV** | Xon exports microvolts; MNE works in volts, so the loader converts. |

### Artifact rejection: why four mechanisms

| Mechanism | Catches | Note |
|---|---|---|
| Amplitude / flat (peak-to-peak) | Movement, electrode pops, dead channels | Krigolson-matched |
| **Gradient** (sample-to-sample slope) | Fast steps/jumps that peak-to-peak can miss | Krigolson-matched |
| Variance z-score (> 3) | Epochs far noisier than that recording's norm | Adaptive, within-recording |
| Muscle z-score (> 3, on > 30 Hz power) | EMG/jaw/neck tension | **Critical** — see 1.4 |

Each rejected epoch is **attributed to the channel(s) that triggered it**. That attribution
is what let us diagnose participants whose recordings were being drained by a single
electrode (see `4_OUTPUTS_AND_ANALYSIS.md`).

---

## 1.3 The FOOOF fit

| Setting | Value | Rationale |
|---|---|---|
| `fooof.freq_range` | **[1, 40] Hz** | Lower bound = epoch length limit; **upper bound 40 Hz deliberately avoids the EMG-dominated band** (see 1.4). |
| `fooof.aperiodic_mode` | **fixed** (no knee) | Standard for a narrow band like 1–40 Hz. A knee is mainly needed over wider ranges. A knee-mode sensitivity check is a sensible robustness analysis. |
| `fooof.peak_width_limits` | [1, 12] Hz | FOOOF defaults; wide enough for alpha/beta, narrow enough to not absorb the aperiodic component. |
| `fooof.max_n_peaks` | 6 | Prevents over-fitting noise as "peaks", which would bias the slope. |
| PSD method | **Welch**, 4-s windows, 50 % overlap | Standard; averaged over clean epochs. |

**Channel-average rule:** each channel is fit separately, then averaged into the
`AVERAGE_exponent`. **Interpolated channels are fit and reported but excluded from the
average**, because a reconstructed channel is not an independent measurement.

---

## 1.4 The EMG problem (the most important methodological caveat)

Muscle activity overlaps EEG from roughly **20 Hz upward** and is far stronger at high
frequencies — at 40 Hz there is ~5× more power in a non-paralysed than paralysed state.
Because the aperiodic exponent is a *slope*, EMG contamination systematically biases it.

**References:** Whitham et al. (2007), *EMG contamination of EEG*; Muthukumaraswamy (2013),
*High-frequency brain activity and muscle artifacts in MEG/EEG: a review and
recommendations*.

**What we do about it (three layers):**

1. Cap the FOOOF fit at **40 Hz**.
2. Notch out **60 Hz** mains and harmonics.
3. Reject epochs on **> 30 Hz muscle z-score**.

**What we do *not* claim:** that EMG is eliminated. It is *mitigated*. This is also the most
plausible reason the **movie** condition is less reliable than rest — eyes-open viewing adds
ocular and muscle activity.

---

## 1.5 ICA is OFF by default

`artifacts.run_ica: false`. ICA needs many more channels than 7 to separate sources
meaningfully; at 7 channels it is underpowered and can remove real signal. We rely instead
on **bad-channel interpolation + epoch-level rejection**. The code path exists and works if
a future montage has more electrodes.

---

## 1.6 Reliability & statistics

| Analysis | Statistic | Source / rationale |
|---|---|---|
| Test–retest across sessions | **ICC(2,1)**, two-way random, absolute agreement, bootstrap 95 % CI | Conventional test–retest statistic. Thresholds: > 0.75 good, > 0.9 excellent. Applied to the aperiodic exponent following **McKeown et al. (2024)**, *Test–retest reliability of spectral parameterization by 1/f characterization using SpecParam*, **Cerebral Cortex** 34:bhad482. |
| Internal consistency vs duration | **Split-half** (odd vs even epochs), **Spearman-Brown** corrected | Epoch-increment reliability approach used in EEG power-spectrum reliability work. Target ≥ 0.90. |
| Rest vs movie value | Paired contrast + **95 % CI + Cohen's d_z** | Small-n pilot: estimation over p-values. A non-significant result is "inconclusive", not "no difference". |
| Scalp region | **Friedman** omnibus + **Holm**-corrected pairwise Wilcoxon | Non-parametric, appropriate for small n and repeated measures across regions. |
| Agreement | **Bland–Altman** (bias + 95 % limits) | Standard test–retest agreement plot. |

### Pseudoreplication — the statistical rule of this codebase

Each participant contributes multiple recordings (2 sessions × 2 conditions). Treating those
as independent subjects **inflates significance**. Every group-level test therefore
**aggregates to one value per participant first**. Pooled descriptive tables mix
sessions/conditions and must not be read as independent samples.

*(An earlier version of the rest-vs-movie contrast was pseudoreplicated and reported
−0.026, p = 0.44. The corrected participant-level result is +0.002, 95 % CI [−0.076,
+0.080], p = 0.95.)*

---

## 1.7 Two different "how many minutes are enough?" questions

This distinction was a genuine source of confusion and matters for interpretation.

| Question | Metric | Column | Cohort result |
|---|---|---|---|
| Does the estimate stop *changing* (is it precise)? | Odd vs even halves agree within tolerance | `minutes_to_stabilize` | median **14.25 min** (22/39 reached it) |
| Does it reach its *final value* (unbiased)? | Running estimate within tolerance of full-length value | `minutes_to_converge` | median **17.0 min** |
| Does it rank people consistently? | Split-half / adjacent-minute ICC | reliability curve | target met by **~1 min** |

**The key insight:** reliability (rank-ordering) is achieved almost immediately, but the
**absolute value keeps drifting for 10–17 minutes**. Short recordings can be *precise but
biased low*. So: short segments are fine for **comparing people**; longer recordings are
needed for **absolute individual values**.

`analysis.stabilization_tolerance` (**0.02**) sets how strict "settled" is. This was
deliberately tightened from 0.1 — a loose tolerance declared "settled at 1 minute" while
the curve was still visibly climbing. The report prints a **sensitivity table** across
tolerances rather than committing to one number.

---

## 1.8 What this study design can and cannot support

- ✅ **Reliability and consistency** of the Xon aperiodic exponent.
- ❌ **Absolute accuracy** — no simultaneous research-grade EEG reference was recorded, so
  there is no ground-truth exponent to compare against.
- ❌ **Regional/source claims** — 7 channels, no temporal or occipital coverage; regional
  patterns are also partly reference-dependent.
- ❌ **Clinical inference** — healthy adults only, n = 10.

---

## 1.9 Software

Preprocessing with **MNE-Python** (Gramfort et al. 2013). Spectral parameterization with
**FOOOF/specparam** (Donoghue et al. 2020). Statistics with **SciPy**; bootstrap CIs
computed internally (`reporting/stats.py`).
