# Usage guide

Everything the pipeline does, and every file it produces.

## 1. Install / run — three equivalent paths

| You want… | Do this |
|---|---|
| The simplest thing, no setup | `./run.sh` (macOS/Linux) or `run.bat` (Windows) |
| A real installed command | `pip install .` then `xon-pipeline …` |
| A clickable interface | `pip install ".[gui]"` then `xon-pipeline gui` |
| No install at all | `pip install -r requirements.txt` then `python -m xon_aperiodic.cli …` |

The launcher builds a private virtual environment in `.venv` on first run, so nothing is
installed system-wide and re-running is safe.

## 2. Commands

```bash
xon-pipeline run                     # process the input folder in config.yaml
xon-pipeline run --input-dir DIR --output OUT
xon-pipeline run --input ONE_FILE.xdf
xon-pipeline run --set section.key=value ...   # override any config setting
xon-pipeline run --no-stats          # skip cohort statistics/report
xon-pipeline streams FILE.xdf        # list the streams in a file (if auto-detect misfires)
xon-pipeline gui                     # launch the offline GUI
xon-pipeline config                  # print the fully-resolved configuration
```

`--set` accepts any dotted config path, e.g.:

```bash
xon-pipeline run \
  --set artifacts.reference=average \
  --set fooof.freq_range=[2,45] \
  --set high_offender.enabled=true \
  --set artifacts.run_ica=true
```

## 3. Preparing your data

Put `.xdf` recordings in the input folder (default `data/`, override with `--input-dir`).
Name them so the pipeline can read the metadata, e.g. `P004_S002_rest.xdf`:

- **participant** — `P004` (pattern `metadata.patterns.participant`)
- **session** — `S002` → session 2 (pattern `metadata.patterns.session`, handles the 3-digit `S001/S002` scheme)
- **condition** — `rest` / `movie` (pattern `metadata.patterns.condition`; `film`/`video` alias to `movie`)

If your naming differs, either edit those regex patterns in `config/config.yaml`, or provide
a `manifest.csv` (see `config/manifest_example.csv`) that maps each file explicitly — the
manifest overrides filename parsing.

## 4. What each stage does (in order)

1. **Load** the `.xdf`, auto-detecting the EEG stream and reading real electrode labels.
2. **Crop** to the task window (config `crop`; disable with `--set crop.start_sec=null`).
3. **Montage** (`standard_1020`) for interpolation / referencing.
4. **Filter** — 0.1 Hz high-pass + 60/120 Hz notch.
5. **Detect bad channels** — robust variance z-score + `annotate_amplitude` (flat/railing).
6. **ICA** — off by default (underpowered at 7 channels).
7. **Interpolate** bad channels (average of good channels), flag them, exclude from the average.
8. **Reference** — keep device ear-clip (default), or `average` / a channel.
9. **Epoch** — 1 s windows, 100 ms overlap.
10. **Reject artifacts** — amplitude (>100 µV), gradient (>10 µV/ms), variance-z, muscle-z,
    each attributed to the offending channel(s).
11. **FOOOF** — fit the 1–40 Hz aperiodic slope per channel → exponent.
12. **Exponent-based rejection** (two-pass) — drop a channel whose *final* exponent is
    implausibly flat (<0.5), re-fit so reject-value = report-value.
13. **High-offender rejection** (optional) — drop a channel causing >50% of a session's
    rejected epochs, gated to only fire when overall rejection ≥15%.
14. **Block** analysis + a **duration curve** (exponent on all/odd/even epochs at
    increasing lengths) that feeds the cohort reliability-vs-length analysis.
15. **Cohort** statistics + figures + report across all files.

## 5. Outputs (in the output folder)

Per recording (`<id>` = e.g. `P004_S2_rest`):

| File | What it is |
|---|---|
| `aperiodic_results_<id>.csv` | per-channel + AVERAGE exponent, full recording + blocks |
| `peak_table_<id>.csv` | oscillatory peaks found by FOOOF |
| `epoch_qc_<id>.csv` | every epoch: kept/rejected and why |
| `durationcurve_<id>.csv` / `.png` | exponent (all/odd/even) at increasing clean minutes |
| `diagnostic_<id>.png` | PSD + per-channel exponents + epoch QC |
| `block_exponents_<id>.png` | exponent over time |
| `qc_report_<id>.html` | **human-readable per-recording report** |

Cohort-level:

| File | What it is |
|---|---|
| `master_everything.csv` | one wide row per recording — settings, rejection counts, per-channel detail |
| `combined_aperiodic_results.csv` | all per-channel rows, long format |
| `stats_quality.csv`, `stats_reliability.csv`, `stats_regional.csv`, `stats_summary.csv` | statistics tables |
| `fig_*.png` | publication figures (condition, test-retest, regional, reliability-vs-duration, quality) |
| `gallery.html` | one-page contact sheet of every recording's diagnostic figure |
| `stats_reliability_by_duration.csv` | split-half + test-retest ICC at each recording length |
| `cohort_report.html` | **the report to read / hand to a mentor** |
| `pipeline_run.log` | full run log |

## 6. Reading the results

The headline number for a recording is the exponent in the row where
`segment == "full"` and `channel == "AVERAGE"` (also `AVERAGE_exponent` in the master CSV).
Lower = flatter spectrum = more excitation (the Alzheimer's concern). A trustworthy value
has high `r_squared` (≥0.9) and a reasonable clean-minute count.

To diagnose a surprising result, open `master_everything.csv` and sort by
`pct_epochs_rejected`; the `worst_reject_channel` and per-channel `*_pct_of_rejected_epochs`
columns tell you whether one electrode is to blame.

## 7. Testing

```bash
pip install pytest
pytest              # runs the full suite on synthetic data (no patient data needed)
```
