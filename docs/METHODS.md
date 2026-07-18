# Methods & references

The pipeline's choices are grounded in published work so results are defensible and
citable. This document maps each step to its source.

## Acquisition & preprocessing (Xon protocol)

Filtering, epoching, and epoch-rejection parameters follow the Boere & Krigolson lab's
Xon validation convention:

- Band-limited preprocessing with a **0.1 Hz high-pass** and mains **notch** (50/60 Hz).
- **1000 ms epochs with 100 ms overlap.**
- Epoch exclusion when **peak-to-peak amplitude > 100 µV** or the **sample-to-sample
  gradient > 10 µV/ms**. Our gradient test reproduces Krigolson's published artifact-
  rejection routine (`MATLAB-EEG-preProcessing`), scaled to µV/ms (a 40 µV/sample step at
  250 Hz equals 10 µV/ms).
- **No re-referencing by default** — the device's A2 ear-clip reference is retained, as in
  the Xon papers.

References:
- Boere et al. (2025), *Scientific Reports* (aphantasia Xon study; PMC12711949).
- Boere, Copithorne & Krigolson (2025), *Experimental Brain Research*.
- Boere et al. (2026), *Journal of Applied Physiology*.

*Caveat:* those studies report band-power (δ/θ/α/β) measures, not the aperiodic exponent,
and do not interpolate channels. Interpolation and the exponent analysis here are additions
appropriate to this study's aims, flagged transparently.

## Bad channels, interpolation, referencing

- Bad-channel detection: robust variance z-score plus MNE's `annotate_amplitude`
  (flat/railing). A stability guard prevents the low-channel-count variance z-score from
  flagging a majority of channels.
- Interpolation: unweighted mean of the good channels (a spherical-spline neighbour circle
  is unreliable at 7 electrodes). Interpolated channels are flagged and **excluded from the
  across-channel average**, because a reconstructed channel is a linear combination of the
  others, not an independent measurement (cf. PREP, Bigdely-Shamlo et al. 2015; autoreject,
  Jas et al. 2017).
- Spherical-spline interpolation and bad-channel handling implemented with **MNE-Python**
  (Gramfort et al. 2013, *Front. Neurosci.*).

## Spectral parameterization (the aperiodic exponent)

- Welch PSD, then the **FOOOF / specparam** model to separate the aperiodic (1/f) component
  from oscillatory peaks. The **aperiodic exponent** is the outcome (lower = flatter
  spectrum = more excitation; the excitation/inhibition marker of interest in Alzheimer's).
- Default fit band **1–40 Hz**, chosen to capture the 1/f slope while diluting the muscle
  (EMG) band that contaminates higher frequencies.

References:
- Donoghue et al. (2020), *Parameterizing neural power spectra into periodic and aperiodic
  components*, **Nature Neuroscience** 23:1655–1665 (the FOOOF/specparam method).
- Whitham et al. (2007); Muthukumaraswamy (2013) — scalp EEG above ~20 Hz is heavily EMG,
  which flattens the spectrum and biases the exponent downward (the artifact this pipeline
  guards against).

## Reliability vs recording length ("how few minutes are enough")

Two standard reliability measures are computed as a function of how much clean data is used:

- **Split-half internal consistency** — the exponent is estimated on odd vs even epochs at
  each cumulative duration, correlated across recordings, and Spearman-Brown corrected to
  full length. Acceptable ≥ 0.90. This mirrors the epoch-increment odd-even reliability
  approach used in EEG power-spectrum reliability work (e.g. reliability/sensitivity studies
  of the EEG power spectrum as a biomarker).
- **Between-session test–retest ICC(2,1)** — session 1 vs session 2 agreement at each
  duration; ICC ≥ 0.75 is "good." The pipeline reports the shortest recording length that
  reaches each target.

References:
- McKeown et al. (2024), *Test–retest reliability of spectral parameterization by 1/f
  characterization using SpecParam*, **Cerebral Cortex** 34:bhad482 (aperiodic ICCs > 0.70;
  data-duration reliability at 1–5 min).
- Test–Retest Reliability of EEG Aperiodic Components in Resting and Mental Task States
  (2024), *Brain Topography*.

## Statistics reported

- Descriptive measurement quality (exponent distribution, fit r², clean-data retention).
- Full-length between-session test–retest reliability (ICC), Pearson r, mean absolute
  session difference.
- Rest vs movie (quiet vs noisy) paired contrast (paired t / Wilcoxon, Cohen's dz).
- Regional summary (frontal / central / parietal) and a non-parametric Friedman test.
- Reliability vs recording length (above).

Statistical tests use SciPy; ICC(2,1) is implemented from the standard two-way random-
effects ANOVA formulation (Shrout & Fleiss 1979).
