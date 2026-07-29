# 4 — Outputs & analyses

*What every file contains, what every analysis answers, and how to read them. Includes the
complete `master_everything.csv` data dictionary.*

---

## 4.1 What a run produces

```
outputs/
├── cohort_report.html          ★ START HERE — the readable summary
├── gallery.html                every recording's diagnostic image, one page
├── master_everything.csv       ★ ONE WIDE ROW PER RECORDING (163 columns)
├── combined_aperiodic_results.csv   long format: one row per channel × segment
├── figures/                    11 publication-quality PNGs (300 dpi)
├── statistics/                 the numbers behind each figure
├── per_recording/              granular per-file outputs
├── logs/                       full console log of the run
├── figures.pdf                 all figures in one PDF
├── *_standalone.html           self-contained (images inlined) — emailable
└── xon_results_bundle_*.zip    everything, zipped
```

**Two-file rule:** open `cohort_report.html` to *understand* the run; open
`master_everything.csv` to *analyse* it.

---

## 4.2 `master_everything.csv` — data dictionary

One row per recording. **163 columns.** Grouped below.

### A. Identity (7)
| Column | Meaning |
|---|---|
| `subject_id` | e.g. `P004_S2_rest` — unique key |
| `file_stem`, `input_file` | source filename / full path |
| `participant`, `session`, `condition` | parsed from filename or manifest |
| `status`, `error_message` | `ok` or `error` + reason (**failed files still appear**) |

### B. Data yield & QC (11)
| Column | Meaning |
|---|---|
| `original_duration_min` | length before cropping |
| `clean_minutes` | minutes of data that survived QC |
| `epochs_before_qc` | epochs created |
| `epochs_after_amp_flat`, `epochs_dropped_amp_flat` | after / dropped by amplitude+flat |
| `epochs_dropped_gradient` | dropped by the gradient rule |
| `epochs_flagged_variance`, `epochs_flagged_muscle` | dropped by adaptive z-score rules |
| `epochs_final_clean` | epochs used for the fit |
| `pct_epochs_rejected`, `pct_epochs_kept` | **the headline QC number** |

### C. The result (5)
| Column | Meaning |
|---|---|
| `AVERAGE_exponent` | ★ **the main outcome** — mean exponent across non-interpolated channels |
| `AVERAGE_exponent_sd` | spread across channels (large ⇒ inconsistent across scalp) |
| `AVERAGE_offset` | aperiodic offset (overall power) |
| `AVERAGE_r_squared` | fit quality; **< 0.9 deserves a look** |
| `AVERAGE_n_channels_averaged` | how many channels contributed |

### D. How long until the estimate settles (2)
| Column | Meaning |
|---|---|
| `minutes_to_stabilize` | odd/even halves agree → **precise**. Blank = never reached within this recording |
| `minutes_to_converge` | running estimate reaches its full-length value → **unbiased** |

### E. Channel decisions — *why a channel was treated specially* (10)
| Column | Meaning |
|---|---|
| `n_channels_analyzed` | channels that made it into the fit |
| `n_interpolated`, `n_excluded`, `n_exponent_flagged` | counts |
| `bad_channels` | everything flagged, `;`-separated |
| `interpolated_channels` | reconstructed (and **excluded from AVERAGE**) |
| `excluded_channels` | dropped without reconstruction |
| `exponent_flagged_channels` | rejected in PASS 2 for a final exponent < 0.5 |
| `screened_channels` | **caught by the proactive screen** (would have tripped > 50 % of epochs) |
| `worst_reject_channel` | ★ the single channel responsible for the most rejections |
| `worst_reject_channel_share` | ★ **what % of all rejected epochs it accounts for** |

> **These two `worst_*` columns are the fastest way to diagnose a bad recording.**
> If one channel accounts for > 50 % of rejections, that electrode — not the participant —
> is the problem.

### F. Per-channel detail — 15 columns × 7 channels (105)
For each of `F3 F4 C3 C4 Cz P3 P4`:

**Fit results**
| Suffix | Meaning |
|---|---|
| `_exponent`, `_offset` | that channel's aperiodic fit |
| `_r2`, `_fit_error` | fit quality |
| `_n_peaks` | oscillatory peaks found |
| `_logvar` | log-variance (the bad-channel detector's input) |
| `_fit_note` | error text if the fit failed |

**Status**
| Suffix | Meaning |
|---|---|
| `_interpolated` | True ⇒ reconstructed, excluded from AVERAGE |
| `_excluded` | True ⇒ dropped entirely |

**★ Why epochs were rejected — attribution**
| Suffix | Meaning |
|---|---|
| `_amp_flat_hits` | epochs this channel tripped on **amplitude/flat** |
| `_gradient_hits` | … on **gradient** (fast steps) |
| `_variance_hits` | … on **variance z-score** |
| `_muscle_hits` | … on **muscle (>30 Hz) z-score** |
| `_total_reject_hits` | sum of the four |
| `_pct_of_rejected_epochs` | this channel's share of all rejected epochs |

**Worked example — `P002_S2_rest`, 59.8 % of epochs rejected:**

| Channel | amp/flat | gradient | var | muscle | total | % of rejects |
|---|---|---|---|---|---|---|
| F3 | 22 | **583** | 8 | 7 | 620 | 51.9 % |
| **F4** | 25 | **663** | 7 | 0 | 695 | **58.2 %** |
| C4 | 33 | 226 | 0 | 0 | 259 | 21.7 % |
| C3 / Cz / P3 / P4 | ≤ 38 | ≤ 21 | ≤ 12 | ≤ 9 | ≤ 59 | < 5 % |

Read: **F4 and F3 are tripping on *gradient*** (fast steps — an electrode-contact problem),
not on amplitude or muscle. The other five channels are fine. That is an electrode issue,
not a noisy participant — and it's exactly the pattern the bad-channel screen now catches.

### G. Settings used for this run (20)
`data_units_assumed`, `epoch_length_sec`, `epoch_overlap_sec`, `high_pass_hz`,
`notch_freq_hz`, `fooof_freq_lo`, `fooof_freq_hi`, `aperiodic_mode`,
`amplitude_threshold_uv`, `gradient_threshold_uv_per_ms`, `flat_threshold_uv`,
`variance_zscore_threshold`, `muscle_zscore_threshold`, `muscle_hf_hz`, `ica_applied`,
`reference`, `interpolation_method`, `montage`, `exponent_reject_threshold`,
`channel_screen`, `channel_screen_share_pct`.

> **Every row records the parameters that produced it.** To compare two runs, diff these
> columns — no lab notebook required.

---

## 4.3 Per-recording outputs (`per_recording/`)

| File | Contents |
|---|---|
| `diagnostic_<id>.png` | 3 panels: all-channel PSD with fits · per-channel exponents · epoch QC counts |
| `qc_report_<id>.html` | self-contained human-readable QC page for that recording |
| `epoch_qc_<id>.csv` | **every epoch**: index, onset, kept?, rejection reason |
| `aperiodic_results_<id>.csv` | every channel × segment (full + blocks) |
| `peak_table_<id>.csv` | oscillatory peaks: centre frequency, power, bandwidth |
| `durationcurve_<id>.csv/.png` | exponent vs cumulative minutes (all/odd/even) |
| `block_exponents_<id>.png` | exponent per 5-min block — drift over the session |

---

## 4.4 The cohort analyses — what each answers

> **About the numbers in this section.** They come from the **reference run**
> (10 healthy adults, 39 recordings, summer 2026) and are shown only as a worked example
> of how to read each output. **Your run will produce different values** — the analyses and
> how you interpret them are what carry over, not these figures.

### Quality & yield → `fig_quality.png`, `stats_quality.csv`
Fit r² vs % data retained. *(Reference run: mean r² 0.98, median 79 % kept over 39
recordings.)* Shows good fits are obtainable even when a lot of data is rejected.

### Test–retest reliability → `fig_test_retest.png`, `fig_bland_altman.png`, `stats_reliability.csv`
Same person, two sessions. **ICC(2,1)** with bootstrap CI.

| Condition | ICC | 95 % CI | Reading |
|---|---|---|---|
| **Rest** | **0.90** | 0.72–0.98 | excellent |
| Movie | 0.61 | −0.47–0.83 | moderate, **CI too wide to lean on** |

Bland–Altman shows bias and 95 % limits of agreement directly.

### Rest vs movie → `fig_condition_paired.png`, `fig_exponent_by_condition.png`
Paired, participant-level. **Δ = +0.002, 95 % CI [−0.076, +0.080], d_z = 0.01, p = 0.95.**
Two *separate* questions: (a) does the value differ (no evidence — but underpowered), and
(b) is the measurement robust in the noisy condition (less so — see the ICCs).
The paired plot is coloured **by participant**.

### Scalp region → `fig_regional.png`, `fig_montage_head.png`, `stats_regional.csv`
Frontal / central / parietal, participant-level, both conditions.
**Rest: Friedman p = 0.007 (significant). Movie: p = 0.093 (not).**
Caveat printed in the report: with 7 channels and an ear reference, regional patterns are
partly reference-dependent — suggestive, not physiology.

### How few minutes are enough → `fig_reliability_by_duration.png`, `fig_group_exponent_by_duration.png`, `fig_stabilization.png`, `fig_duration_overlay.png`
The headline analysis, and the one most easily misread:

| Curve | Answers | Result |
|---|---|---|
| Split-half (odd vs even) | Is the estimate internally consistent? | **0.943 at 1 min**, 0.94–0.997 throughout |
| Adjacent-minute ICC | Does *rank order* stop changing? | target met by ~1 min |
| Group-mean exponent vs length | Does the *value* plateau? | still climbing for ~10–15 min |
| `minutes_to_stabilize` (dots) | Per-recording precision | **median 14.25 min** (22/39 reached it) |
| `minutes_to_converge` | Per-recording bias | **median 17.0 min** |

> ⚠️ **The one sentence to remember:** reliability (*rank-ordering people*) is achieved in
> about a minute, but the **absolute exponent keeps drifting for 10–17 minutes**. Short
> recordings can be **precise but biased low**. Short segments → fine for comparing people.
> Absolute individual values → record longer.

`settling_sensitivity` prints the settling estimate across tolerances (0.05 / 0.03 / 0.02)
instead of committing to one, because "settled" is a judgment call.

### Demographics (optional, OFF) → `fig_exponent_by_age.png`, `fig_exponent_by_sex.png`
Set `stats.demographics_csv` to a CSV with `participant, age, sex`. Relevant because the
exponent flattens with normal aging.

---

## 4.5 Statistics CSVs

| File | Contents |
|---|---|
| `stats_quality.csv` | descriptives (n, mean, SD, median, IQR, min, max) overall and by condition |
| `stats_reliability.csv` | ICC(2,1), CI, Pearson r, mean absolute session difference |
| `stats_regional.csv` | exponent by scalp region |
| `stats_reliability_by_duration.csv` | the full duration curve: split-half, test–retest ICC, n at each length, mean absolute error to full |
| `stats_summary.csv` | every scalar in one row: contrast, regional test, duration, stabilization, inclusion |

---

## 4.6 How to read a new run in 5 minutes

1. **`cohort_report.html`** → "Key takeaways" at the top.
2. **`pct_epochs_rejected`** in the master CSV — sort descending. Anything > 50 %?
3. For those, check **`worst_reject_channel` / `worst_reject_channel_share`** — one
   electrode, or the whole cap?
4. Check **`screened_channels`** — did the screen already catch and fix it?
5. **`AVERAGE_r_squared`** — anything < 0.9 gets eyes on its `diagnostic_*.png`.
6. **`gallery.html`** — scan all recordings at once for anything visibly odd.

---

## 4.7 Reproducing the poster figures

`archive/poster-scripts/poster_figs.py` regenerates the six poster figures from
`master_everything.csv` with poster-scale fonts and the poster palette.
`archive/poster-scripts/build_poster.py` inserts them into the PowerPoint file. Neither is part of the pipeline —
they read its outputs.
