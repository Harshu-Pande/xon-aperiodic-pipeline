# 2 — Setup, running & troubleshooting

*Two tracks. **Track A** needs no coding at all. **Track B** is for whoever maintains the
code. Start with A.*

---

# TRACK A — No coding required

## A1. One-time setup

You need **Python 3.9 or newer** installed. Check by opening Terminal (Mac) or Command
Prompt (Windows) and typing `python3 --version` (Mac) / `python --version` (Windows).
If it errors, install from <https://www.python.org/downloads/> — tick **"Add Python to
PATH"** on Windows.

Everything else installs itself on first run.

## A2. Running it

| Your computer | Do this |
|---|---|
| **Mac** | Double-click **`Start Here (Mac).command`** |
| **Windows** | Double-click **`Start Here (Windows).bat`** |

A window opens. The **first run takes a few minutes** (it builds a private Python
environment inside the project folder). Later runs start in seconds.

Then, in the GUI:

1. **Browse** → pick the folder holding your Xon recordings.
2. **Browse** → pick where results should go.
3. Adjust settings if needed (all optional — see `3_CODE_WALKTHROUGH.md` for what each does).
4. Click **Run**.

When it finishes, open **`cohort_report.html`** in the output folder. That is the summary
document. `gallery.html` shows every recording's diagnostic image on one page.

## A3. Naming your files

The pipeline reads participant / session / condition **from the filename**:

```
P004_S002_rest.xdf   →  participant P004, session 2, condition rest
P011_S001_movie.xdf  →  participant P011, session 1, condition movie
```

- `rest` and `movie` are the two conditions (`film`/`video` also map to movie).
- **Xon files often have no `.xdf` extension** — that is fine, the default file pattern is
  `*` and non-data files are skipped automatically.
- If filenames can't be fixed, use a **manifest CSV** instead
  (`config/manifest_example.csv` shows the format) and point `metadata.manifest` at it.

## A4. Changing a setting without touching code

Open the GUI and change it there, or open **`config/config.yaml`** in any text editor —
every option is grouped and commented. Save, re-run.

> **Important:** the GUI and command-line overrides apply to *that run only*.
> `config/config.yaml` is the permanent source of defaults.

## A5. Keeping your own changes when the code updates

The launchers auto-update from GitHub. `update.py` does a **hash-based smart merge**: any
file you edited locally is **kept**, and the incoming version is saved next to it as
`*.new` so you can compare. You will not silently lose edits to `config.yaml`.

To skip updating entirely, set the environment variable `XON_NO_UPDATE=1`.

---

# TRACK B — For whoever maintains the code

## B1. Install

```bash
git clone https://github.com/Harshu-Pande/xon-aperiodic-pipeline.git
cd xon-aperiodic-pipeline
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies: `mne`, `fooof`, `pyxdf`, `numpy`, `pandas`, `scipy`, `matplotlib`, `pyyaml`.
Optional extras: `tkinterdnd2` (drag-and-drop in the GUI), `streamlit` (the alternative web
GUI).

## B2. Commands

```bash
# run the whole folder from config
PYTHONPATH=src python -m xon_aperiodic.cli run

# point at specific folders
… run --input-dir /path/to/EEG --output /path/to/results

# a single file
… run --input /path/to/one_recording.xdf

# override any setting for one run (repeatable)
… run --set artifacts.reference=average --set fooof.freq_range=[2,45]

# inspect an .xdf's streams
… streams /path/to/file.xdf

# print the fully-resolved config and exit
… config

# GUIs
… gui        # native desktop (fast, recommended)
… webgui     # Streamlit alternative

# regenerate share formats (PDF / standalone HTML / zip) for a finished run
… export --output /path/to/results
```

Useful `run` flags: `--pattern '*'`, `--recursive` / `--no-recursive`, `--no-stats`,
and `--if-exists overwrite|copy|ask` (what to do when the output folder already has
results; default `overwrite`).

## B3. Tests

```bash
PYTHONPATH="src:examples" python -m pytest tests/ -q
```

13 tests, **all on synthetic data — no patient data required or touched**. The important
one is `test_exponent_recovery`, which generates signals with a *known* exponent (0.7, 1.2,
1.8) and asserts the pipeline recovers it within 0.2. If you change anything in
`spectral.py`, that test is your safety net.

`examples/generate_synthetic_data.py` can also write you a fake cohort to experiment on.

## B4. Where things live

```
config/config.yaml          ← every setting (the one file to edit)
src/xon_aperiodic/
  cli.py            command line
  config.py         loads + validates settings
  io_xdf.py         read .xdf, auto-pick the EEG stream
  metadata.py       filename/manifest → participant, session, condition
  preprocess.py     montage, filter, bad channels, interpolate, ICA, reference
  epoching.py       cut into 1-s epochs
  artifacts.py      4-way epoch rejection + per-channel attribution
  spectral.py       Welch PSD → FOOOF → exponent; duration curves
  pipeline.py       orchestrates ONE recording
  batch.py          many recordings → master CSV
  diagnostics.py    per-recording plots + QC page
  reporting/        cohort stats, figures, HTML report, gallery, exports
  gui.py            native desktop GUI
tests/              synthetic test suite
docs/               this documentation (docs/archive/ = superseded)
update.py           smart updater that preserves local edits
```

---

# TROUBLESHOOTING

### "No files found with pattern '*.xdf'"
Xon exports frequently have **no file extension**. Set the pattern to `*`:
`--set io.file_glob='*'` (this is already the default).

### `ModuleNotFoundError: No module named 'xon_aperiodic'`
Python can't see `src/`. Use the launcher, or prefix commands with `PYTHONPATH=src`.

### "All epochs were rejected"
Usually a **units** problem — the data are already in volts but were read as microvolts.
In order of likelihood:
1. `--set xdf.data_units=V`
2. Raise the amplitude threshold: `--set artifacts.amplitude_threshold_uv=300`
3. Temporarily disable adaptive QC:
   `--set artifacts.variance_zscore_threshold=null --set artifacts.muscle_zscore_threshold=null`

### One participant loses most of their epochs
Look at `worst_reject_channel` and `worst_reject_channel_share` in the master CSV. If one
electrode is responsible for most rejections, the **bad-channel screen** (on by default)
should be catching it — check the `screened_channels` column. If it isn't, lower
`channel_screen.min_epoch_share_pct` (default 50).

### The GUI won't open / Tkinter missing
Use the web GUI instead: `xon-pipeline webgui`. On some Mac Python builds Tkinter is
missing from the interpreter; installing Python from python.org (rather than Homebrew)
usually fixes it.

### The run is slow
Processing is parallel by default (`performance.n_jobs: auto`, capped at
`max_workers: 6`). Lower `max_workers` if the machine runs out of RAM; set
`n_jobs: 1` to debug an error with a clean traceback.

### It crashed on one file and I lost the batch
It didn't — failures are caught per file. That recording gets `status = "error"` and an
`error_message` in the master CSV; everything else still completes.

### Wrong stream picked from the .xdf
Run `xon-pipeline streams yourfile.xdf` to list them, then force one:
`--set xdf.stream_name='Xon EEG'` (or `xdf.stream_type=EEG`).

### Results changed after an update
Compare the **settings columns** in `master_everything.csv` between the two runs — every
run records the parameters it used, so a settings difference is visible directly in the
data. Also check for `*.new` files from the updater.

---

## HIPAA / data-safety notes

- Raw `.xdf` recordings **never leave the machine**. Nothing is uploaded.
- Both GUIs run locally (the web GUI serves only to `127.0.0.1`).
- `.gitignore` excludes data folders and outputs, so recordings can't be committed by
  accident.
- The updater only *downloads* public code; it never uploads anything.
- Outputs are keyed by coded IDs (`P004_S002_rest`) — keep the code↔identity key
  elsewhere, per your IRB.
