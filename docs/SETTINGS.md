# Settings cheat-sheet

There are **three ways** to change any setting — pick whichever you like:

1. **Edit `config/config.yaml`** — the permanent way. Every option is grouped and
   commented there. Change a value, save, re-run.
2. **`--set` on the command line** — a one-off override without editing the file:
   `xon-pipeline run --set channel_screen.enabled=false`
3. **The GUI** (`./run.sh gui`) — the most-tinkered settings are checkboxes/sliders.

`--set` and the GUI never modify `config.yaml`; they only apply to that run. The config
file is always the source of truth for defaults.

---

## "I want to… → change this"

| I want to… | Setting (config.yaml → `--set`) | Default |
|---|---|---|
| Turn OFF the bad-channel screen (on by default) | `channel_screen.enabled` → `--set channel_screen.enabled=false` | `true` |
| Change the screen's trip threshold | `channel_screen.min_epoch_share_pct` | `50` (%) |
| Change how strict "settled" is (how-few-minutes answer) | `analysis.stabilization_tolerance` | `0.02` |
| Turn off exponent-based channel rejection | `exponent_rejection.enabled` | `true` |
| Change the flat-exponent cutoff | `exponent_rejection.threshold` | `0.5` |
| Use average reference instead of the ear clip | `artifacts.reference` (`average`/`Cz`/`ear`) | `ear` (null) |
| Turn ICA on | `artifacts.run_ica` | `false` |
| Change the FOOOF fit band | `fooof.freq_range` → `--set fooof.freq_range=[2,45]` | `[1, 40]` |
| Use a knee in the aperiodic fit | `fooof.aperiodic_mode` (`fixed`/`knee`) | `fixed` |
| Loosen/tighten amplitude rejection | `artifacts.amplitude_threshold_uv` | `100` (µV) |
| Loosen/tighten the gradient reject | `artifacts.gradient_threshold_uv_per_ms` | `10` |
| Change epoch length / overlap | `epoch.length_sec`, `epoch.overlap_sec` | `1.0`, `0.1` |
| Not crop the recording | `crop.start_sec`, `crop.stop_sec` → `--set crop.start_sec=null` | `60`, `1860` |
| Files have no `.xdf` extension | `io.file_glob` → `--set io.file_glob='*'` | `*.xdf` |
| Change how filenames map to participant/session/condition | `metadata.patterns.*` | see file |
| Which condition the scalp-region analysis uses | `stats.region_condition` (`rest`/`movie`/`null`) | `rest` |
| Plot exponent by age & sex | `stats.demographics_csv` → path to a CSV (participant, age, sex) | `null` |

## The bad-channel screen (on by default)

Before epoch rejection, any channel that would trip more than `channel_screen.min_epoch_share_pct`
of the epochs (using the same amplitude/gradient/variance/muscle tests that reject epochs) is
flagged and interpolated first — so one burst-bad channel doesn't drain the recording. The
channel it catches is recorded in the `screened_channels` column of the master CSV. To turn it
off: `--set channel_screen.enabled=false`.

## A note on experimenting

Because you'll be comparing settings a lot: run each configuration into its **own output
folder** so nothing overwrites, then compare the `master_everything.csv` files:

```bash
xon-pipeline run --output out_baseline
xon-pipeline run --output out_noscreen  --set channel_screen.enabled=false
xon-pipeline run --output out_avgref    --set artifacts.reference=average
```
