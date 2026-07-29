# Xon Aperiodic Pipeline

Turn **Xon headset `.xdf` EEG recordings** into the **aperiodic (1/f) exponent** — a candidate
excitation/inhibition marker for Alzheimer's research — with transparent artifact rejection,
granular quality control, publication-quality figures, and cohort statistics.

Point it at a folder of recordings and it does the rest. Everything runs **offline on your own
machine**, so it is safe for patient data.

---

## What do you want to do?

| I want to… | Go here |
|---|---|
| **Run it** (no coding) | [Quick start](#quick-start) below, then **[Setup & Running](docs/2_SETUP_AND_RUNNING.md)** |
| **Run it from a terminal** | [For developers](#for-developers) below, or **[Setup & Running → Track B](docs/2_SETUP_AND_RUNNING.md)** |
| **Change a setting** | [`config/config.yaml`](config/config.yaml) — every option, commented. What each one does: **[Code Walkthrough](docs/3_CODE_WALKTHROUGH.md)** |
| **Understand the science / cite it** | **[Methods & Literature](docs/1_METHODS_AND_LITERATURE.md)** — every setting traced to its paper |
| **Understand the code** | **[Code Walkthrough](docs/3_CODE_WALKTHROUGH.md)** — every module and function, ON or OFF by default |
| **Understand the results** | **[Outputs & Analysis](docs/4_OUTPUTS_AND_ANALYSIS.md)** — every output file + the full master-CSV data dictionary |
| **Fix a problem** | **[Troubleshooting](docs/2_SETUP_AND_RUNNING.md#troubleshooting)** |
| **Read everything in one file** | **[`docs/Xon_Pipeline_Documentation.html`](docs/Xon_Pipeline_Documentation.html)** — self-contained; email it to anyone |

---

## Quick start

### No coding, no admin password (recommended)

Open **Terminal** (⌘-Space → type `Terminal`), paste this one line, press Return:

```bash
cd ~/Desktop && curl -L https://github.com/Harshu-Pande/xon-aperiodic-pipeline/archive/refs/heads/main.zip -o xon.zip && unzip -oq xon.zip && cd xon-aperiodic-pipeline-main && chmod +x scripts/run.sh && ./scripts/run.sh gui
```

It downloads the program, sets itself up, and opens a small app window. Choose your recordings
folder, choose where results go, press **▶ Run**.

Afterwards, just double-click **`Start Here (Mac).command`** (or **`Start Here (Windows).bat`**)
in the folder.

**Then open `cohort_report.html`** in your output folder — that's the summary.

> Windows, or prefer to download-and-double-click? See
> **[Setup & Running](docs/2_SETUP_AND_RUNNING.md)**, which also covers the one-time macOS
> security prompt.

### For developers

```bash
pip install .
xon-pipeline run --input-dir /path/to/recordings --output results
xon-pipeline gui                        # native desktop GUI
xon-pipeline streams FILE.xdf           # inspect an .xdf's streams
xon-pipeline config                     # print the resolved settings
```

Or run without installing (the launcher builds a private `.venv` on first use):

```bash
./scripts/run.sh run --input-dir /path/to/recordings --output results   # macOS/Linux
scripts\run.bat  run --input-dir C:\path\to\recordings --output results  # Windows
```

Try it on **synthetic demo data** — no real recordings needed:

```bash
python examples/generate_synthetic_data.py    # writes a demo cohort to ./data
./scripts/run.sh                              # -> ./outputs/cohort_report.html
```

---

## What you get

**Per recording:** the aperiodic exponent per channel and an across-channel average, a
diagnostic figure, an exponent-vs-recording-length curve, and a self-contained **HTML QC
report** showing what ran, what was cut, and why.

**Per cohort:** `master_everything.csv` (one wide row per recording — every setting used,
per-stage rejection counts, per-channel fits, and *which channel caused each rejection*),
publication figures, statistics CSVs, and a single **`cohort_report.html`** answering:

- **Measurement quality** — fit r², exponent distribution, clean-data retention
- **Test–retest reliability** — ICC(2,1) across each participant's repeat sessions
- **Quiet vs noisy** — rest vs movie paired contrast
- **Scalp region** — frontal / central / parietal
- **How few minutes are enough** — reliability vs recording length

---

## Configuration

Every setting lives in **[`config/config.yaml`](config/config.yaml)**, grouped and commented.
Change it there (permanent), tick it in the GUI, or override for one run:

```bash
xon-pipeline run --set artifacts.reference=average --set fooof.freq_range=[2,45]
```

**Filenames drive the metadata.** `P004_S002_rest.xdf` → participant P004, session 2,
condition rest. Editable regex patterns in the config; or drop in a `manifest.csv`
(see [`config/manifest_example.csv`](config/manifest_example.csv)) to override parsing
entirely. No code changes needed.

---

## Data safety (HIPAA)

- Recordings **never leave your machine**; the pipeline makes **zero network calls**, including
  the GUI.
- `.gitignore` blocks `data/`, `outputs/`, and EEG file types, so patient data can't be
  committed by accident.
- Validated against **synthetic recordings with a known exponent** (`examples/`, `tests/`), so
  no real data is needed to verify it works.
- The auto-updater only *downloads* public code, and **preserves any file you edited**
  (your version is kept; the incoming one is saved alongside as `*.new`).

---

## Project layout

```
xon-aperiodic-pipeline/
├── Start Here (Mac).command      ← double-click to run (macOS)
├── Start Here (Windows).bat      ← double-click to run (Windows)
├── config/config.yaml            ← THE settings file
├── docs/                         ← documentation (start here)
├── src/xon_aperiodic/            ← the pipeline
│   ├── io_xdf.py                   load .xdf, auto-detect the EEG stream
│   ├── metadata.py                 filename → participant / session / condition
│   ├── preprocess.py               montage, filter, bad channels, interpolate, reference
│   ├── epoching.py · artifacts.py  epoching + 4-way rejection w/ per-channel attribution
│   ├── spectral.py                 Welch PSD → FOOOF exponent + duration curves
│   ├── pipeline.py                 one recording, orchestrated
│   ├── batch.py                    many recordings → master CSV
│   ├── diagnostics.py              per-recording plots + QC report
│   ├── reporting/                  cohort stats, figures, cohort report
│   ├── cli.py · gui.py             command line + desktop GUI
├── scripts/                      ← launchers & updater (run.sh, run.bat, update.py)
├── tests/                        ← synthetic test suite (no patient data)
├── examples/                     ← synthetic data generator + sample outputs
└── archive/                      ← superseded material, kept for history
```

---

## Documentation

| Doc | Read it for |
|---|---|
| **[1 — Methods & Literature](docs/1_METHODS_AND_LITERATURE.md)** | why every setting is what it is, with citations |
| **[2 — Setup & Running](docs/2_SETUP_AND_RUNNING.md)** | install, run, troubleshoot — non-coder **and** coder tracks |
| **[3 — Code Walkthrough](docs/3_CODE_WALKTHROUGH.md)** | every module and function; ON or OFF by default |
| **[4 — Outputs & Analysis](docs/4_OUTPUTS_AND_ANALYSIS.md)** | every output file + the full master-CSV data dictionary |

**Or read everything in one place:**
**[`docs/Xon_Pipeline_Documentation.html`](docs/Xon_Pipeline_Documentation.html)** — all four
documents in a single self-contained HTML file with sidebar navigation, search and diagrams.
No repo, no internet, nothing to install — email it to anyone and it just works.
Regenerate it with `python3 docs/build_site.py` after editing the markdown.

---

## Tests

```bash
PYTHONPATH="src:examples" python -m pytest tests/ -q
```

15 tests, all on synthetic data. The key one, `test_exponent_recovery`, generates signals with a
*known* exponent and asserts the pipeline recovers it — your safety net if you change the
spectral code.

---

## License

MIT — see [LICENSE](LICENSE).
