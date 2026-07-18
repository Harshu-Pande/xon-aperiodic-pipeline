# Getting started

Two ways to install. The first avoids every macOS security prompt and needs no
administrator password — recommended for lab computers. Both take a few minutes the
first time and are quick thereafter.

---

## Option A — recommended (one line, no security prompts, no admin)

macOS flags *anything* downloaded through a web browser with a security warning — it's
not specific to this software. Installing through Terminal sidesteps that entirely.

1. Open **Terminal** (press ⌘-Space, type `Terminal`, press Return).
2. Copy the line below, paste it into Terminal, and press Return:

```bash
cd ~/Desktop && curl -L https://github.com/Harshu-Pande/xon-aperiodic-pipeline/archive/refs/heads/main.zip -o xon.zip && unzip -oq xon.zip && cd xon-aperiodic-pipeline-main && chmod +x run.sh && ./run.sh gui
```

That downloads the program to your Desktop, sets it up, and opens the app in your web
browser. The first run takes a minute or two while it installs; after that it's fast.

**Next time**, just open the `xon-aperiodic-pipeline-main` folder on your Desktop and
double-click **`Start Here (Mac).command`** — no warning will appear, because the setup
already cleared the download flag.

**To update later**, paste the same line again; it refreshes to the newest version.

---

## Option B — download and double-click

1. On the GitHub page, click the green **Code** button → **Download ZIP**, then
   double-click the ZIP to unzip it.
2. Open the `xon-aperiodic-pipeline` folder and double-click **`Start Here (Mac).command`**
   (Windows: **`Start Here (Windows).bat`**).
3. The first time, macOS may say the file is *"from an unidentified developer."* This is
   the standard warning for any downloaded file. To proceed **without an admin password**:
   **right-click** (or Control-click) the file → **Open** → **Open**. You only do this once.

If your Mac is managed by IT and even right-click → Open is blocked, use **Option A**
instead — it never triggers the warning.

---

## Opening it again later (after the first install)

You do **not** repeat the install command. Two easy ways:

- Double-click **`Open Xon Pipeline`** on your Desktop (a shortcut is created for you the
  first time you run it), **or**
- open the `xon-aperiodic-pipeline-main` folder and double-click **`Start Here (Mac).command`**.

**It stays up to date automatically — but keeps your changes.** Each time you open it, it
quietly pulls the latest *code* from GitHub (your data and results are never touched; only
public code is fetched, so it stays HIPAA-safe). Crucially, **any file you edited yourself
is preserved** — if you changed a setting in `config/config.yaml`, or even edited the source
code, the update will *not* overwrite it. The newer version of anything you changed is saved
right next to it as `<file>.update`, so you can adopt the new version later if you want.
Files you didn't touch update normally; new features are added. To freeze everything (e.g.
while writing up results), set the environment variable `XON_NO_UPDATE=1`.

## Running it

1. Put your recordings in a folder (anywhere — they can be named anything, and it's fine
   if they don't end in `.xdf`).
2. A small app window opens. **Drag your recordings folder (or the individual files) onto
   the drop zone** at the top. Prefer buttons? Use **Choose folder…** / **Choose files…**,
   or type/paste a path — it cleans up quotes and spaces automatically.
3. Leave the output as-is to save inside the program's `outputs` folder, or drag/choose a
   different folder.
4. The defaults are sensible. To change anything, open the **Settings** tab — everything is
   there, each field with a hover **?** explanation.
5. Press **▶ Run pipeline**. Progress shows live in the window; when it finishes it opens
   the cohort report, and buttons let you open the **gallery** and the **results folder**.

**Running a second time?** If the output folder already holds a previous run, the app asks
whether to **overwrite** it or **save this run as a new dated copy** (so you never lose the
earlier results). Choosing a different output folder always leaves earlier runs untouched.

## Reading your results

Open the output folder. The three files most people want are at the top:

- **`cohort_report.html`** — the plain-language summary of the whole study.
- **`gallery.html`** — every recording's diagnostic figure on one page.
- **`master_everything.csv`** — one row per recording with all the numbers.

Everything granular (per-recording tables, per-recording QC reports, individual figures)
is tucked into the `per_recording/`, `figures/`, and `statistics/` sub-folders so the top
level stays clean.

## Sharing results (slides, email, PDF)

When a run finishes, the app makes share-ready files automatically (and the buttons at the
bottom let you make them anytime):

- **`figures.pdf`** — every publication figure, one per page. Drop straight into slides.
- **`cohort_report_standalone.html`** / **`gallery_standalone.html`** — single self-contained
  files (images baked in) you can email; they open on any computer with no setup.
- **`xon_results_bundle_<date>.zip`** — everything (report, gallery, figures, statistics)
  zipped for handing to a colleague.
- **Save report as PDF** — the button opens the report in your browser; press ⌘P (or Ctrl+P)
  and choose "Save as PDF" for a clean, formatted PDF.

The individual figures are also PNGs in the `figures/` folder.

## If something isn't working

- **No recordings found** — the folder is wrong or empty; re-select it with 📁 Browse.
- **It's asking me something in the Terminal window** — it shouldn't; if it does, send a
  screenshot and it'll be sorted.
- **Anything else** — a screenshot of the browser page or the Terminal window is usually
  all that's needed to diagnose it.
