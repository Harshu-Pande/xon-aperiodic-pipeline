> **Note (v1.0):** this walkthrough was written during the artifact-rejection audit and
> describes the reasoning behind each step. Since then the pipeline adopted the
> mentor + Boere/Krigolson decisions now shipped as defaults in `config/config.yaml`:
> FOOOF fit range **1–40 Hz** (was 15–50), **ear (A2) reference** kept by default (was
> average), **0.1 Hz** high-pass, **1 s / 100 ms** epochs, amplitude **100 µV** + gradient
> **10 µV/ms**, and ICA off. The explanations below still apply; where a number differs,
> the config file is the source of truth.

# The Xon Aperiodic Pipeline, Explained in Plain English

*A walkthrough for a non-programmer — what every artifact step does, why it's there,
whether the experts (MNE + the aperiodic-exponent literature) actually recommend it,
and an honest verdict on whether it's helping or possibly hurting your data.*

---

## 0. First, what are we even measuring?

You are measuring one number per channel: the **aperiodic exponent**.

Think of the EEG power spectrum as a graph of "how much energy is at each frequency."
On a log-log graph, brain activity forms a **downward slope** — lots of energy at low
frequencies, less and less as you go higher. The *steepness* of that slope is the
exponent.

- **Steep slope (high exponent, ~1–3)** = the "healthy" brain pattern. More inhibition.
- **Flat slope (low exponent, ~0–0.5)** = flatter spectrum. More excitation — and this
  is the Alzheimer's concern (excitation/inhibition imbalance).

**The catch that explains almost all your headaches:** *muscle activity also flattens
the slope.* When a jaw, neck, or forehead muscle twitches, it dumps broadband energy
across the high frequencies, which lifts the right-hand side of the graph and makes the
slope look flatter — i.e., it *fakes a low exponent.* So "low exponent" can mean
"excitation" (real, what you want) **or** "muscle contamination" (fake, what you don't).
Everything the artifact pipeline does is, ultimately, an attempt to tell those two apart.

---

## 1. The big picture: every step, in order

```
  LOAD the .xdf file
    │
  MARK non-brain channels (accelerometer, BIP, etc.) so they're ignored
    │
  CROP to the 30-min task (drop setup time)
    │
  MONTAGE — give each electrode a 3D position on the scalp
    │
  FILTER — high-pass 1 Hz (remove drift) + notch 60/120 Hz (remove power-line hum)
    │
  ── ARTIFACT HANDLING STARTS HERE ──
    │
  DETECT bad channels  (variance z-score + flat/dead check)
    │
  ICA  — try to subtract eye/heart/muscle "sources"
    │
  INTERPOLATE the bad channels (rebuild them from neighbors)
    │
  AVERAGE REFERENCE  (re-center every channel against the group average)
    │
  EPOCH — chop into 2-second pieces
    │
  EPOCH QC — throw out 2-sec pieces that are too big / flat / high-variance / muscley
    │
  FOOOF — fit the slope on each channel, over 15–50 Hz
    │
  EXPONENT REJECTION — if a channel's final slope is implausibly flat, redo without it
    │
  REPORT — one exponent per channel + an across-channel average
```

The rest of this document walks each **artifact** step and gives it a traffic light:

- 🟢 **Standard & safe** — recommended, low risk to the exponent.
- 🟡 **Defensible but watch it** — reasonable, but can bias the exponent in your setup.
- 🔴 **The real levers** — the steps most likely responsible for "the data looks worse."

---

## 2. The steps, one at a time

### 2.1 🟢 Filtering — high-pass 1 Hz + notch 60/120 Hz
*(`apply_filter`, STEP 2)*

- **What it does:** The high-pass removes very slow drifts (sweat, electrode settling).
  The notch removes the 60 Hz hum from wall power (and its 120 Hz echo).
- **Why:** Slow drifts wreck the next step (ICA literally can't work with them), and
  power-line hum is a fake spike, not brain.
- **What the experts say:** MNE explicitly recommends a **1 Hz high-pass before ICA** —
  we do exactly that. ✔️
- **Does it help or hurt your exponent?** **Helps / neutral.** Crucially, your notches
  are at 60 and 120 Hz, which are *above* your 50 Hz fitting ceiling — so the notch never
  carves a hole inside the range you actually fit. Safe.

### 2.2 🟢 Detect flat / dead channels — `annotate_amplitude`
*(`detect_flat_railing_channels`, part of STEP 2b)*

- **What it does:** Flags any electrode that is essentially a flatline (disconnected) or
  pinned to the rails (broken) for more than 20% of the recording.
- **Why:** A dead electrode is not brain; it must be caught before it poisons the average.
- **What the experts say:** This is MNE's own built-in "is this channel dead?" function.
  Textbook. ✔️
- **Help or hurt?** **Helps.** One tuning note we already fixed: we require a channel to
  be flat for 0.1 s continuously (not the 5 ms default), because normal brain waves briefly
  cross zero and a too-short window would wrongly call healthy channels "flat."

### 2.3 🟡 Detect bad channels — variance z-score
*(`detect_bad_channels`, STEP 2b, threshold `BAD_CHANNEL_ZSCORE = 4.0`)*

- **What it does:** Compares how "loud" each channel is to the others. A channel that is
  wildly louder (railing/noisy) or wildly quieter (near-dead) than the group gets flagged.
- **Why:** It's a cheap, dependency-free way to catch grossly bad electrodes.
- **What the experts say:** MNE's tutorials and tools like PREP use exactly this idea —
  automatic detection by "abnormal variance," often z > 3.
- **Help or hurt? — WATCH IT (🟡).** Here's the honest catch: a z-score asks "how far from
  the group is this channel?" — but with **only 7 channels**, the "group" is tiny and
  unstable. One genuinely noisy channel drags the average, which can make a *healthy*
  channel look like an outlier, or hide a bad one. The threshold (4.0) is deliberately
  loose to avoid over-flagging, but this step is inherently shaky at 7 channels. It is
  probably doing little harm, but it is **not a strong safeguard** here.

### 2.4 🔴 ICA — Independent Component Analysis
*(`run_ica`, STEP 2c)*

- **What it does:** ICA tries to "un-mix" the recording into separate underlying sources
  (e.g., "this pattern is eye-blinks, that one is heartbeat, that one is muscle"), then
  deletes the artifact sources and rebuilds the EEG without them.
- **Why:** On a full 64-channel cap, ICA is the gold standard for pulling out blinks and
  heartbeats.
- **What the experts say:** ICA's power comes from having **many** channels. The math can
  only find as many "sources" as you have channels — with **7 channels you get ~7 sources**,
  which is nowhere near enough to cleanly isolate muscle from brain. MNE and the literature
  both treat ICA as a dense-array method.
- **Help or hurt? — A REAL LEVER (🔴).** On your headset ICA is a weak first pass at best.
  At worst, when it "removes a muscle component" it may be removing a blend that includes
  real brain signal, subtly reshaping the very slope you're measuring. **Low value, nonzero
  risk.** This is a prime candidate for the ablation test in §4 — you may find turning it
  off changes little (or even helps stability).

### 2.5 🟢/🟡 Interpolation — rebuild bad channels from neighbors
*(`interpolate_bad_channels`, STEP 2b-i)*

- **What it does:** Takes a channel we flagged as bad and mathematically reconstructs it as
  a weighted blend of the surrounding good electrodes (spherical-spline interpolation).
- **Why:** It keeps the montage "complete" so the average reference and topography behave.
- **What the experts say:** Spherical-spline interpolation is MNE's standard method. ✔️
  BUT — the literature (PREP, autoreject) is clear that an interpolated channel is a
  *reconstruction*, not a real measurement.
- **Help or hurt?** **Safe, because we handle it correctly.** We interpolate to keep the
  reference clean, but we **flag** interpolated channels and **exclude them from the
  averaged exponent** — because a rebuilt channel's slope is just a blend of its neighbors,
  not independent evidence. That's the right call. The only 🟡 is that at 7 channels a
  "neighbor blend" is coarse, so don't over-read an interpolated channel's individual value.

### 2.6 🔴 Average reference — re-center against the group
*(`apply_average_reference`, STEP 2d)*

- **What it does:** EEG voltage is always "relative to something." Average referencing
  makes every channel relative to the *average of all channels*. It subtracts the shared,
  group-wide signal from each electrode.
- **Why:** On multi-channel montages it's standard and makes channels comparable.
- **What the experts say:** The reference is standard **but not neutral** — the published
  work is explicit that *"power spectra may change for different references."* Changing the
  reference genuinely changes the numbers, including the aperiodic slope.
- **Help or hurt? — THE BIGGEST QUIET LEVER (🔴).** With a full cap, subtracting the
  average barely touches any single channel. With **7 channels**, the average is dominated
  by just a few electrodes, so subtracting it **substantially reshapes each channel's
  spectrum.** Your own `--no_avg_ref` test on P009 proved this: F3's exponent moved
  0.345 → 0.650 when you turned referencing off, while central/parietal channels moved the
  other way (Cz 2.14 → 1.72, P4 1.54 → 0.84). That is the reference **inflating** central
  channels and **deflating** frontal ones — a swing of up to ~0.7 in the exact number you
  report. This isn't a bug; it's what average referencing *does* on few channels. **It is a
  genuine methodological choice to raise with your mentor,** because it silently changes
  everyone's exponent, not just F3's.

### 2.7 🟢 Epoch QC — drop bad 2-second pieces
*(`reject_artifacts`, STEP 4: amplitude / flat / variance / muscle)*

- **What it does:** After chopping the recording into 2-sec epochs, it discards any epoch
  that is (a) too big peak-to-peak (>150 µV — a movement/jump), (b) flat, (c) a variance
  outlier vs the other epochs, or (d) a **muscle** outlier — measured as excess energy
  above 30 Hz.
- **Why:** Even on good channels, *some* 2-sec windows are contaminated (a swallow, a
  shift). Dropping just those windows is gentler than throwing out a whole channel.
- **What the experts say:** Epoch-level amplitude/flat rejection is textbook. The **muscle
  (>30 Hz) rejection is especially on-point** for you, because muscle is precisely the
  high-frequency contaminant that fakes a low exponent.
- **Help or hurt?** **Helps — this is arguably your best artifact defense.** It targets the
  exact problem (muscle) at the finest grain (per 2-sec window) instead of nuking channels.
  If anything, this is the step to *lean on more* and the channel-level rejections to lean
  on less.

### 2.8 🔴 Exponent-based channel rejection — the circular one
*(two-pass logic + `DETECT_BAD_EXPONENT`, `EXPONENT_REJECT_THRESHOLD = 0.5`, STEP 6b)*

- **What it does:** After fitting, if a real channel's slope is implausibly flat (below
  0.5), it assumes muscle contamination, throws the channel out, and re-runs so the number
  it rejected on is the same number it reports. *(We just rebuilt this to fix the old bug
  where it judged a channel at the wrong stage.)*
- **Why:** Your mentor's "bad-channel threshold" idea — some channels come back near 0.2,
  which screams muscle, so drop them.
- **What the experts say:** There is **no standard method that rejects a channel based on
  the study's own outcome.** This is a homegrown step.
- **Help or hurt? — USE WITH EYES OPEN (🔴).** The danger is **circularity**: you're
  measuring the exponent, then deleting channels *because of* their exponent. If your
  hypothesis is "Alzheimer's lowers the exponent," a rule that deletes low exponents can
  literally erase the effect you're hunting — or manufacture a cleaner-looking one. We kept
  the cutoff very conservative (0.5, well below any plausible real value) specifically to
  only catch the obvious ~0.2 muscle junk. It is defensible *as a conservative junk filter*,
  but it is the **least standard** thing in the pipeline and should be reported transparently
  (which channels, what threshold) in any writeup.

---

## 3. The honest audit — is all this helping or hurting?

Your instinct ("we're doing so much; how much actually helps?") is a good scientific one.
Here is my honest ranking, most-likely-hurting first:

| Rank | Step | Verdict | Why |
|---|---|---|---|
| 1 | **FOOOF range 15–50 Hz** | 🔴 biggest issue | This range sits *inside the muscle band.* The literature is blunt: "most scalp EEG above 20 Hz might simply be EMG." You are fitting your slope in the frequency band most contaminated by muscle — so muscle leaks straight into your headline number, and no amount of downstream cleaning fully undoes it. |
| 2 | **Average reference** | 🔴 quiet distorter | At 7 channels it reshapes each exponent by up to ~0.7 (your own P009 test). Silently changes every result. |
| 3 | **Exponent-based rejection** | 🔴 circular | Rejecting on the outcome can bias the effect you're studying. Conservative, but non-standard. |
| 4 | **ICA** | 🟡 low value | Underpowered at 7 channels; small risk of shaving real signal. |
| 5 | **Variance z-score channel detection** | 🟡 shaky at 7 ch | Unstable "group" of 7; weak safeguard, probably harmless. |
| — | Filtering, flat/dead detection, interpolation-with-exclusion, **epoch muscle QC** | 🟢 keep | Standard, safe, and the epoch muscle QC directly fights your core problem. |

**The single most important takeaway:** the biggest lever isn't any cleaning step — it's
the **fitting range**. If you fit 15–50 Hz, you are choosing to measure the slope in the
dirtiest possible band, and then spending five artifact steps trying to claw back the mess.
The published recommendation (Donoghue 2020 and follow-ups) is to think carefully about the
range; many resting-EEG aperiodic studies fit something like **1–40 Hz or 2–45 Hz** to
capture the true 1/f while diluting the muscle band. You declined this change earlier (to
keep parity with the sleep pipeline), which is a legitimate choice — but given your current
frustration, **re-testing a lower/broader range is probably the highest-value single
experiment you can run.**

---

## 4. How to actually find out — run the experiment, don't guess

You don't have to take my ranking on faith. The pipeline already has switches to turn each
step on/off, so you can do a proper **ablation**: run the *same file* several ways and watch
what happens to (a) the average exponent, (b) how much channels agree
(`aperiodic_exponent_sd` — lower = more stable), and (c) fit quality (`r_squared` — higher
= the slope actually fits).

Pick **one representative recording** and run these, comparing the `AVERAGE` row each time:

```bash
# 0. Baseline — everything on (what you run now)
python xon_xdf_aperiodic_pipeline_7.py --input <file> --output out_baseline

# 1. Turn OFF average reference  (tests the §2.6 lever)
python xon_xdf_aperiodic_pipeline_7.py --input <file> --output out_noref --no_avg_ref

# 2. Turn OFF ICA  (tests the §2.4 lever)
python xon_xdf_aperiodic_pipeline_7.py --input <file> --output out_noica --no_ica

# 3. Turn OFF automatic channel detection + interpolation
python xon_xdf_aperiodic_pipeline_7.py --input <file> --output out_nochan \
    --no_bad_channel_detection --no_interpolate
```

For the **fitting range** (the #1 lever) and the **exponent-rejection** step, there's no CLI
flag yet — they're set at the top of the file. To test them, open the script and change:

- `FOOOF_FREQ_RANGE = [15, 50]` → try `[2, 40]` and `[1, 45]`, re-run, compare.
- `DETECT_BAD_EXPONENT = True` → `False`, re-run, see if your numbers barely move (if so,
  the circular step isn't earning its keep).

**What "better" looks like:** across recordings you *trust*, the winning configuration is
the one where clean channels give **stable** exponents (low SD), **good fits** (high r²),
and where obviously-muscley frontal channels aren't wildly different from central ones. If a
step you remove barely changes the numbers, it's not helping — drop it for simplicity. If
removing it makes things noticeably worse, it's earning its place.

> Tip: I can add proper `--fooof_min`/`--fooof_max` and `--no_exponent_reject` command-line
> flags so you can sweep these without editing the file each time. Say the word.

---

## 5. One-paragraph summary for your mentor

> "The pipeline does standard MNE preprocessing (1 Hz high-pass, notch, spherical-spline
> interpolation of dead channels, epoch-level amplitude/muscle rejection) plus three
> non-trivial choices worth discussing: (1) we fit the aperiodic slope over 15–50 Hz, which
> overlaps the EMG band and is the most likely source of artifact-driven low exponents;
> (2) average referencing on only 7 electrodes measurably reshapes each channel's exponent
> (±~0.7 in our tests), so it's not a neutral step here; and (3) we optionally reject
> channels whose *own* exponent is implausibly flat, which risks circularity and is kept
> deliberately conservative. Before trusting group results, we're running an ablation to see
> which steps actually improve stability and fit quality versus which are just adding moving
> parts."

---

### Sources / further reading
- Donoghue et al. 2020, *Parameterizing neural power spectra into periodic and aperiodic
  components*, Nature Neuroscience — the FOOOF/specparam method paper.
- Whitham et al. 2007 & Muthukumaraswamy 2013 — scalp EEG above ~20 Hz is heavily muscle.
- MNE-Python tutorials: *Handling bad channels* (interpolation), *Repairing artifacts with
  ICA* (1 Hz high-pass before ICA).
- "How to Improve the Reliability of Aperiodic Parameter Estimates in M/EEG" (bioRxiv 2025)
  and reference-effect studies — reference choice and fitting range both shift aperiodic
  estimates.
```
