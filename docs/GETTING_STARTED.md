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

## Running it

1. Put your recordings in a folder (anywhere — they can be named anything, and it's fine
   if they don't end in `.xdf`).
2. When the app opens in your browser, click **📁 Browse** next to "Folder of recordings"
   and select that folder. (No need to type or paste a path — but if you prefer to, the
   box accepts a pasted path and cleans up quotes and spaces automatically.)
3. The common settings have sensible defaults; adjust anything you like, or open
   **Advanced settings** for the full set. Every field has a small **?** with an explanation.
4. Press **▶ Run pipeline**. Results, figures, and a report appear on the page and are
   saved to your output folder.

## Reading your results

Open the output folder. The three files most people want are at the top:

- **`cohort_report.html`** — the plain-language summary of the whole study.
- **`gallery.html`** — every recording's diagnostic figure on one page.
- **`master_everything.csv`** — one row per recording with all the numbers.

Everything granular (per-recording tables, per-recording QC reports, individual figures)
is tucked into the `per_recording/`, `figures/`, and `statistics/` sub-folders so the top
level stays clean.

## If something isn't working

- **No recordings found** — the folder is wrong or empty; re-select it with 📁 Browse.
- **It's asking me something in the Terminal window** — it shouldn't; if it does, send a
  screenshot and it'll be sorted.
- **Anything else** — a screenshot of the browser page or the Terminal window is usually
  all that's needed to diagnose it.
