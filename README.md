# Xon Aperiodic Pipeline

Turn **Xon headset `.xdf` EEG recordings** into the **aperiodic (1/f) exponent** — the
excitation/inhibition marker at the heart of this Alzheimer's research — with transparent
artifact rejection, granular quality control, publication-quality figures, and statistics.

The goal of the study this serves: show that a wearable EEG headset can recover the
aperiodic exponent **accurately, reliably, and in a few minutes in a noisy clinic room**,
instead of needing 8 hours of clean overnight sleep EEG. This pipeline is the analysis
engine for that claim — point it at a folder of recordings and it figures everything out,
runs the agreed processing, and produces results you could put in a paper.

---

## What you get

For **each recording**: the aperiodic exponent per channel and an across-channel average,
a diagnostic figure, an exponent-vs-recording-length plot, and a self-contained
**HTML QC report** showing exactly what ran, what got cut, and why.

For the **whole cohort**: a wide `master_everything.csv` (one row per recording with every
setting, per-stage rejection counts, and per-channel detail), a long results CSV, a set of
**publication figures**, statistics CSVs, and a single **`cohort_report.html`** that
answers the study's questions:

- **Measurement quality / yield** — fit r², exponent distribution, clean-data retention.
- **Test–retest reliability** — ICC(2,1) across each participant's repeat sessions.
- **Quiet vs noisy** — rest vs movie paired contrast (does it survive movement/noise?).
- **Scalp region** — frontal / central / parietal comparison.
- **How few minutes are enough** — reliability (split-half + test-retest ICC) as a function
  of recording length, with the shortest length that reaches "good" reliability.

---

## Quick start

### Easiest setup — no coding, no admin password (recommended)

Open **Terminal** (⌘-Space → type `Terminal`), paste this one line, and press Return:

```bash
cd ~/Desktop && curl -L https://github.com/Harshu-Pande/xon-aperiodic-pipeline/archive/refs/heads/main.zip -o xon.zip && unzip -oq xon.zip && cd xon-aperiodic-pipeline-main && chmod +x run.sh && ./run.sh gui
```

It downloads the program, sets it up, and opens a small app window. **Drag your recordings
folder onto it** (or click Choose folder), then press **▶ Run**. On later days, double-click
**`Start Here (Mac).command`** in the folder — no security prompt appears because this
method never quarantines the files.

Prefer to download-and-double-click instead, or on Windows? See the step-by-step guide,
which also covers the one-time macOS security prompt (and how to clear it without an admin
password): **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

---

### For developers

Install as a package and use the command line:

```bash
pip install .
xon-pipeline run --input-dir /path/to/xdf_folder --output results
xon-pipeline gui                              # native desktop GUI (drag-and-drop)
xon-pipeline webgui                           # Streamlit web GUI (alternative)
xon-pipeline streams FILE.xdf                 # inspect a file's streams
```

Or clone-and-run without installing (the launcher builds a private `.venv` on first use):

```bash
./run.sh run --input-dir /path/to/xdf_folder --output results   # macOS/Linux
run.bat  run --input-dir C:\path\to\xdf_folder --output results  # Windows
```

Try it on **synthetic demo data** (no real data needed):

```bash
python examples/generate_synthetic_data.py    # writes a demo cohort to ./data
./run.sh                                       # -> ./outputs/cohort_report.html
```

Everything runs on your machine, so it is safe for real patient data.

---

## Configuration — one file

Every setting lives in [`config/config.yaml`](config/config.yaml). It is heavily commented
and grouped in plain English. The defaults reproduce the Boere/Krigolson Xon validation
protocol plus this lab's mentor-approved choices, so most people never touch it.

Override any single setting from the command line without editing the file:

```bash
xon-pipeline run --set artifacts.reference=average --set fooof.freq_range=[2,45]
```

New to the settings, or planning to tinker a lot? See the plain-English
[**settings cheat-sheet**](docs/SETTINGS.md) — an "I want to X → change Y" table covering
the bad-channel screen, reference, ICA, FOOOF band, thresholds, and more. Or just tick
them in the GUI.

**How files are understood.** The pipeline reads each file's participant / session /
condition from its **name** using editable regex patterns in the config
(`P004_S002_rest.xdf` → participant P004, session 2, condition rest). If naming changes in
future, edit one pattern — or drop in a `manifest.csv` (see `config/manifest_example.csv`)
that overrides the parsing. No code changes ever needed.

---

## HIPAA / data safety

- Real Xon `.xdf` files contain protected patient data. **They are never committed to git
  and never leave the machine.** The `.gitignore` blocks `data/`, `outputs/`, and every
  EEG file type by default.
- The pipeline makes **zero network calls** — it runs fully offline, including the GUI.
- Because real data can't be used for testing, the pipeline is validated against
  **synthetic recordings with a known exponent** (see `examples/` and `tests/`).

---

## Project layout

```
xon-aperiodic-pipeline/
├── config/config.yaml            # THE single settings file
├── run.sh / run.bat              # one-command launchers (no git/experience needed)
├── src/xon_aperiodic/
│   ├── config.py                 # load + validate config
│   ├── io_xdf.py                 # load .xdf, auto-detect the EEG stream
│   ├── metadata.py               # participant/session/condition (regex + manifest)
│   ├── preprocess.py             # montage, filter, bad channels, interpolate, ICA, reference
│   ├── epoching.py, artifacts.py # epoching + 4-way rejection with per-channel attribution
│   ├── spectral.py               # Welch PSD -> FOOOF exponent + duration curve
│   ├── pipeline.py               # one file, bad-channel screen + two-pass exponent logic
│   ├── batch.py                  # many files -> combined + master CSV
│   ├── diagnostics.py            # per-file plots + HTML QC report
│   ├── reporting/                # cohort stats, publication figures, cohort report
│   ├── cli.py                    # `xon-pipeline` command
│   └── gui.py                    # offline native desktop GUI
├── tests/                        # pytest suite (synthetic data)
├── examples/                     # synthetic data generator + demo
└── docs/                         # USAGE.md and the methods walkthrough
```

See [`docs/USAGE.md`](docs/USAGE.md) for a full walkthrough of every command and output,
and [`docs/PIPELINE_WALKTHROUGH.md`](docs/PIPELINE_WALKTHROUGH.md) for the methodology and
the rationale behind each artifact-handling choice.

---

## What was ported from the original script

This is a modular, installable rebuild of the single-file `xon_xdf_aperiodic_pipeline.py`.
Every validated behaviour is preserved: XDF stream auto-detection, `standard_1020` montage,
robust-variance + `annotate_amplitude` bad-channel detection, average/spline interpolation
(flagged and excluded from the average), the manually-implemented gradient reject matched to
Krigolson's routine, the two-pass **exponent-based** channel rejection (fit → reject on the
final value → refit), per-channel rejection attribution, block analysis, and the wide master
CSV. A proactive **bad-channel screen** (on by default) was added so a burst-bad channel is
interpolated before epoch rejection instead of draining the recording. Two correctness fixes
were added along the way: a stability guard on the variance bad-channel detector at low
channel counts, and excluding reconstructed channels from the average reference / epoch-drop
decision.
