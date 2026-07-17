# Getting started — the no-coding guide

This is for people who have **never used a terminal** and don't want to. Follow it
exactly and you'll have results in a few minutes.

## What you need

- A Mac (or Windows) computer.
- A folder containing your Xon `.xdf` recordings.

## Step 1 — Download the pipeline

If you already have the `xon-aperiodic-pipeline` folder on your computer, skip to Step 2.

Otherwise, on the GitHub page click the green **Code** button → **Download ZIP**. Then
double-click the downloaded ZIP to unzip it. You now have a folder called
`xon-aperiodic-pipeline`.

## Step 2 — Put your recordings in one folder

Make a folder for your recordings (for example, a folder called **EEG** inside your
**Downloads**), and put all your `.xdf` files in it. They can be named anything, and it's
fine if they don't end in `.xdf`.

## Step 3 — Start the app (no typing)

**On a Mac:** open the `xon-aperiodic-pipeline` folder and **double-click the file named
`Start Here (Mac).command`**.

- A black window opens and shows some text — that's normal. The **first time only**, it
  spends 1–2 minutes setting itself up. Leave it alone; don't close it.
- Then a page automatically opens in your web browser. That's the app.

> If macOS says *"cannot be opened because it is from an unidentified developer"*:
> right-click the file → **Open** → **Open**. You only do this once.

**On Windows:** double-click **`Start Here (Windows).bat`** instead. Same idea.

## Step 4 — Run it

In the browser page:

1. On the left, the **Folder of recordings** box should point at your recordings folder.
   If not, put the correct folder there. (Easiest way to get a folder's location on a Mac:
   right-click the folder in Finder, hold the **Option** key, and choose
   **"Copy as Pathname"**, then paste it into the box.)
2. Leave all the other options as they are the first time.
3. Press the big blue **▶ Run pipeline** button.
4. Wait. When it's done you'll see 🎈 and your results appear right on the page — a table,
   a report, and figures. They're also saved to the output folder (by default a **"Xon
   results"** folder on your Desktop).

## Step 5 — Read your results

The most important file is **`cohort_report.html`** in the output folder — double-click it
to open it in your browser. It walks through everything in plain language: how reliable the
recordings were, rest vs movie, how few minutes were needed, and more.

Each recording also gets its own **`qc_report_<name>.html`** you can open the same way.

## Changing settings later

Once you're comfortable, the app's left sidebar lets you flip things on and off with
checkboxes and sliders (like the high-offender channel rejection). For a full list of what
each setting does, see [`SETTINGS.md`](SETTINGS.md). You never have to edit code.

## If something goes wrong

- **"No files found"** — your recordings folder path is wrong, or the box is pointing at an
  empty folder. Double-check Step 4.1.
- **The black window closed instantly** — try again; if it keeps happening, tell Claude what
  the window said.
- **Anything else** — take a screenshot of the black window or the browser page and send it
  over; that's usually enough to sort it out.
