# Documentation

**The easiest way to read all of this: open [`Xon_Pipeline_Documentation.html`](Xon_Pipeline_Documentation.html)
in any browser.** It contains everything below in one file — searchable, with diagrams, and
completely self-contained (no internet, no other files, nothing to install). You can email
that single file to anyone.

Prefer plain text or reading on GitHub? The same content lives in these four documents:

| # | Document | Read it for |
|---|---|---|
| 1 | [Methods & Literature](1_METHODS_AND_LITERATURE.md) | Why every setting is what it is, with the papers behind each one. The EMG caveat, the pseudoreplication rule, and what this study design can and cannot support. |
| 2 | [Setup & Running](2_SETUP_AND_RUNNING.md) | Installing and running it — **Track A** needs no coding, **Track B** is for whoever maintains the code. Includes the full troubleshooting list. |
| 3 | [Code Walkthrough](3_CODE_WALKTHROUGH.md) | Every module and function: what it does, why, and whether it is **ON or OFF by default**. |
| 4 | [Outputs & Analysis](4_OUTPUTS_AND_ANALYSIS.md) | Every output file, every cohort analysis, and the complete `master_everything.csv` data dictionary. |

---

### Common questions → where to look

| Question | Go to |
|---|---|
| How do I just run this? | 2 → *Track A* |
| Why 1–40 Hz? Why 100 µV? | 1 → *Acquisition & preprocessing settings* |
| What does this setting do? | 3 (grouped by module) |
| What is this column in the CSV? | 4 → *data dictionary* |
| Why did this recording lose so many epochs? | 4 → `worst_reject_channel`, then 2 → *Troubleshooting* |
| Is this measuring E/I balance? | 1 → *The measure* (short answer: putative, and debated) |
| How many minutes of data do we need? | 1 → *Two different "how many minutes" questions* |

---

### Notes

- **`archive/`** holds superseded documentation from earlier versions. It is kept for history
  and is **not** current — every file there carries a banner saying so.
- **`build_site.py`** regenerates the HTML file from the four markdown documents:
  ```bash
  python3 docs/build_site.py
  ```
  Edit the markdown, re-run that, and the HTML updates. Don't hand-edit the HTML.
- Numbers quoted in document 4 come from the **reference run** (10 adults, 39 recordings) and
  are there as a worked example of how to read each output — **your runs will differ**.
