# 3 — Code walkthrough

*Every module, every function that matters, what it does, why, and whether it's ON or OFF
by default. Terse on purpose.*

**Legend:** 🟢 ON by default · 🔴 OFF by default · ⚙️ always runs · 🔧 config key

---

## The flow, end to end

```
 .xdf file
    │
    ▼
 io_xdf.py        load, auto-pick EEG stream, µV → V
    ▼
 metadata.py      filename → participant / session / condition
    ▼
 preprocess.py    types → crop → montage → filter → detect bad channels → (ICA)
    ▼
 artifacts.py     🟢 bad-channel SCREEN (would-trip share)
    ▼
 ┌──────────── _process()  (re-runnable) ─────────────┐
 │ interpolate bads → reference → epoch → reject      │
 │ → Welch PSD → FOOOF per channel → AVERAGE          │
 └────────────────────────────────────────────────────┘
    ▼   (PASS 2 🟢 if any channel's final exponent < 0.5 → interpolate it, re-run)
 spectral.py      duration curve (all / odd / even)
    ▼
 diagnostics.py   per-recording PNG + QC html
    ▼
 batch.py         all recordings → master_everything.csv
    ▼
 reporting/       cohort stats → figures → cohort_report.html
```

**Why `_process()` is a nested re-runnable function:** if a channel is rejected on its
exponent, everything downstream of interpolation must be recomputed so that *the exponent
we rejected on is exactly the exponent we report*. No stale numbers.

---

## `config.py` — settings

| Item | Notes |
|---|---|
| `DEFAULTS` dict | Full default config lives in code, so the pipeline runs even with a missing/partial `config.yaml`. |
| `load_config()` | Reads `config/config.yaml`, deep-merges onto `DEFAULTS`. |
| `Config.get(section, key)` / `.section()` | Every module receives `cfg` explicitly — **no global constants anywhere**. |
| `validate()` ⚙️ | Rejects impossible settings early (bad interpolation method, inverted `freq_range`, overlap ≥ epoch length) rather than failing deep in a run. |
| `resolve_path()` | Makes relative paths work regardless of where you launched from. |

---

## `io_xdf.py` — reading the recording

| Function | Does | Why |
|---|---|---|
| `load_xdf_as_raw()` ⚙️ | Loads the chosen stream into MNE, converts to volts | Entry point |
| `choose_xdf_stream()` ⚙️ | Picks the EEG stream by name/type, else **heuristic score** | Xon files contain several streams; scoring avoids hard-coding |
| `extract_channel_names()` | Reads real electrode labels, falls back to `Ch1..ChN` | |
| `list_xdf_streams()` | Powers `xon-pipeline streams` | Debugging which stream is which |
| `unit_scale_to_volts()` | 🔧 `xdf.data_units` (**uV**) | Wrong units ⇒ everything rejected |

`_srate_from_timestamps()` also **warns if LSL timestamps are jittery**, since MNE assumes
regular sampling.

---

## `metadata.py` — who is this recording?

Regex patterns 🔧 `metadata.patterns` extract participant / session / condition from the
filename. `condition_aliases` maps `film`/`video` → `movie`. A **manifest CSV**
🔧 `metadata.manifest` (default `None`) overrides filenames entirely when naming is
inconsistent.

---

## `preprocess.py` — cleaning the continuous signal

| Step | Default | What / why |
|---|---|---|
| `mark_obvious_non_eeg_channels()` | ⚙️ | Retypes ECG/EOG/EMG/ACC/**BIP**/trigger channels so they don't pollute EEG steps. Xon's `BIP` aux input is *not* scalp EEG. |
| `crop_recording()` | 🔧 `crop.start_sec 60`, `stop_sec 1860` | Trims setup/end. Disable with `--set crop.start_sec=null`. |
| `apply_montage()` | 🟢 `standard_1020` | Gives electrodes scalp positions. **EEG channels with no montage position are reclassified `misc` and dropped** — prevents a positionless channel poisoning the reference/PSD. |
| `apply_filter()` | 🟢 0.1 Hz HP + 60 Hz notch (+harmonics) | See doc 1. |
| `detect_bad_channels()` | 🟢 `bad_channel_zscore 3.0` | Robust variance z-score (median/MAD on log-variance). |
| `detect_flat_railing_channels()` | 🟢 `use_annotate_amplitude` | MNE `annotate_amplitude`; `min_duration` **0.1 s** not the 5 ms default, so normal oscillation zero-crossings aren't misread as flat. |
| `interpolate_bad_channels()` | 🟢 method **`average`** | Bad channel ← unweighted mean of good channels. Chosen over `spline` because a spline's neighbour circle is unreliable at 7 electrodes. |
| `run_ica()` | 🔴 **OFF** | Underpowered at 7 channels. Works if you ever get more electrodes. |
| `apply_reference()` | 🔧 `reference: null` = **device ear-clip (A2)** | `average` or a channel name also supported. |

### Two guards worth knowing about

**1. Variance-detector stability guard.** If the detector flags more than `n_channels // 3`
channels, it flags **none**. Rationale: with 7 near-identical-variance channels a hair's
difference explodes into a huge z-score and the detector flags a *majority* — nonsense for a
test whose premise is that bad channels are the minority. Epoch-level QC handles those cases.

**2. Interpolated channels are excluded from the average reference.** An average-interpolated
channel literally *is* the mean of the good channels; including it in an average reference
makes the reference equal to that channel and **zeroes it out**, which then reads as "flat"
and rejects every epoch. This was a real bug, now guarded.

---

## `epoching.py`

`make_awake_epochs()` ⚙️ — fixed-length epochs, 🔧 `epoch.length_sec 1.0` /
`overlap_sec 0.1`, over good EEG channels only.

---

## `artifacts.py` — rejection & the attribution that matters

### `reject_artifacts()` ⚙️ — four mechanisms, in order

| # | Mechanism | Default | Drops an epoch when… |
|---|---|---|---|
| 1 | Amplitude / flat | 🟢 100 µV / 1 µV | peak-to-peak out of range |
| 2 | **Gradient** | 🟢 10 µV/ms | max sample-to-sample slope exceeds it (Krigolson-matched) |
| 3 | Variance z | 🟢 > 3 | epoch variance is an outlier *within this recording* |
| 4 | Muscle z | 🟢 > 3 on > 30 Hz | high-frequency power is an outlier (EMG) |

Mechanisms 3–4 need ≥ 5 surviving epochs; below that they're skipped (a z-score over 4
epochs is meaningless).

**Per-channel attribution** — for every mechanism it records *which channel triggered it*,
producing `{CH}_amp_flat_hits`, `_gradient_hits`, `_variance_hits`, `_muscle_hits`. This is
what distinguishes "one bad electrode is poisoning whole epochs" from "the whole cap is
noisy", and it is how the P002 diagnosis was made.

**`ignore_channels`** — interpolated channels still get attribution counts but **do not
drive the drop decision**, since a reconstructed channel isn't an independent measurement.

If everything is rejected, the error message names the three likely fixes rather than
raising a bare exception.

### `channels_over_reject_share()` 🟢 — the proactive screen

🔧 `channel_screen.enabled: true`, `min_epoch_share_pct: 50`

Runs *before* rejection. Applies the **same four criteria** and returns any channel that
would trip more than 50 % of epochs, so it can be **interpolated first**.

**Why it exists:** the variance detector looks at *overall* variance across the recording; a
channel that is fine on average but spikes in bursts slips past it and then silently drains
the recording at the epoch stage. Detection criteria ≠ rejection criteria was the bug. On
real data this recovered a participant from ~88 % → ~34 % rejection.

**Safety rail:** it refuses to fire if it would leave fewer than 3 good channels.

---

## `spectral.py` — PSD → FOOOF → exponent

| Function | Default | Notes |
|---|---|---|
| `compute_psd()` ⚙️ | Welch, 4-s window, 50 % overlap | Averaged over clean epochs |
| `fit_fooof()` ⚙️ | 🔧 `freq_range [1,40]`, `aperiodic_mode fixed` | Auto-clamps the range to what the PSD actually covers |
| `fit_segment()` ⚙️ | | Fits every channel + an `AVERAGE` row. **Interpolated channels are fit and reported but excluded from AVERAGE.** |
| `extract_peak_table()` ⚙️ | | Oscillatory peaks (centre freq, power, bandwidth) → `peak_table_*.csv` |
| `compute_duration_curve()` 🟢 | 🔧 `analysis.reliability_step_sec 30`, max 20 points | Exponent using the first *k* epochs, three ways: **all / odd / even** |
| `duration_stabilization()` | 🔧 `stabilization_tolerance 0.02` | First length where \|odd − even\| ≤ tol **and stays there** → `minutes_to_stabilize` |
| `duration_convergence_to_full()` | same tol | First length within tol of the **full-length** value → `minutes_to_converge` |

> **Performance note:** the duration curve computes the per-epoch Welch PSD **once**, then
> each cumulative point is a mean over the first *k* spectra plus one FOOOF fit — instead of
> re-running Welch at every duration. This was verified to be **bit-for-bit identical**
> (max difference 0.00e+00) to the slow version.

**Odd/even is deliberately independent** — comparing two independent halves is a genuine
precision signal, unlike comparing a recording to its own endpoint (which is circular; that's
what `duration_convergence_to_full` does, and it's labelled descriptive for that reason).

---

## `pipeline.py` — one recording, orchestrated

Order (STEP numbers appear in the console log):

1. Load → crop → montage → filter
2. `detect_bad_channels` 🟢 + `annotate_amplitude` 🟢
3. ICA 🔴
4. **STEP 3b — bad-channel screen** 🟢
5. **PASS 1** → `_process()`: interpolate → reference → epoch → reject → PSD → FOOOF
6. **STEP 6b — exponent-based rejection** 🟢 🔧 `exponent_rejection.threshold 0.5`
   → if a non-interpolated channel's final exponent < 0.5, add to bads and **re-run
   `_process()`** (PASS 2). Refuses if it would leave < 3 good channels.
7. Block analysis 🟢 🔧 `analysis.block_length_min 5.0`
8. Duration curve 🟢
9. Write per-recording outputs + build the master row

`_build_master_record()` flattens **everything** — settings used, QC counts, per-channel
fits, per-channel rejection attribution — into one wide row. That's why the master CSV is
self-documenting: every row records the parameters that produced it.

**Interpolation happens BEFORE epoch rejection** (this was explicitly checked — it is the
correct order, so a recoverable channel is fixed rather than draining the recording).

---

## `batch.py` — many recordings

| Item | Default | Notes |
|---|---|---|
| `find_xdf_files()` | 🔧 `io.file_glob '*'`, `recursive: true` | Skips non-data extensions (csv/png/html…) so a broad `*` is safe |
| Parallelism | 🟢 `n_jobs auto`, `max_workers 6` | `auto` = CPUs − 1, capped. Workers forced single-threaded so N workers don't oversubscribe the CPU |
| Error handling | ⚙️ | One file failing → `status="error"` + `error_message` in the master row; **the batch continues** |
| `order_master_columns()` | ⚙️ | Puts the ~25 most-read columns first |
| `output_has_results()` / `timestamped_sibling()` | 🔧 `--if-exists` | Overwrite vs save-a-copy |

---

## `reporting/` — cohort analysis

### `stats.py`
`compute_all()` runs everything: `quality_summary`, `reliability` (ICC(2,1) + bootstrap CI),
`condition_contrast` (paired, CI + d_z), `regional_test` (Friedman + Holm),
`reliability_by_duration` (split-half + test-retest curves), `adjacent_duration_icc`,
`group_exponent_by_duration`, `stabilization_summary`, `settling_sensitivity`,
`demographics_analysis` 🔴 (needs 🔧 `stats.demographics_csv`).

**`_regional_by_participant()` is the anti-pseudoreplication helper** — one row per
participant before any group test. 🔧 `stats.region_condition: rest`.

### `figures.py`
`build_all()` writes up to 13 PNGs at 300 dpi. Palette: **rest = blue, movie = orange**;
regions = purple/teal/rose. Every function **guards on data availability and returns `None`**
rather than crashing, so a small cohort simply produces fewer figures.

### `report.py`
`build_cohort_outputs()` → stats CSVs + figures + `cohort_report.html`. The report embeds
plain-English interpretation, the pseudoreplication caveat, and a **Limitations** section.

### `gallery.py` / `export.py`
One-page contact sheet of every diagnostic image; `export_all()` makes `figures.pdf`,
`*_standalone.html` (images inlined as base64 — emailable), and a bundle `.zip`.

---

## `gui.py` 🟢 / `gui_web.py` 🔴

Native Tkinter desktop GUI (fast, native folder picker, every setting exposed, basics up
top / rest under Advanced). `gui_web.py` is an optional Streamlit fallback
(`xon-pipeline webgui`) for machines where Tkinter is broken.

---

## `update.py` — updates that don't destroy edits

`smart_merge()` compares **hashes**: files you never edited are updated in place; files you
*did* edit are **kept**, with the new version written alongside as `*.new`. Skip with
`XON_NO_UPDATE=1`. Covered by `tests/test_updater.py`.

---

## Known quirks

- `webgui` (Streamlit) is optional and not installed by default — `pip install streamlit`.
- `figures.py` participant colours come from a 10/20-colour map; **beyond ~12 participants
  hues start repeating.**
- `crop` defaults (60–1860 s) assume the ~30-min protocol. For other lengths set
  `crop.start_sec: null` or the run will be silently truncated. A warning prints if the
  stream length is more than 2 min from `crop.expected_duration_min`.
