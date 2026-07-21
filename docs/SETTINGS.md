# Settings cheat-sheet

There are **three ways** to change any setting — pick whichever you like:

1. **Edit `config/config.yaml`** — the permanent way. Every option is grouped and
   commented there. Change a value, save, re-run.
2. **`--set` on the command line** — a one-off override without editing the file:
   `xon-pipeline run --set high_offender.enabled=true`
3. **The GUI** (`./run.sh gui`) — the most-tinkered settings are checkboxes/sliders.

`--set` and the GUI never modify `config.yaml`; they only apply to that run. The config
file is always the source of truth for defaults.

---

## "I want to… → change this"

| I want to… | Setting (config.yaml → `--set`) | Default |
|---|---|---|
| **Screen bad channels before rejecting** (fixes 80%-rejected files) | `channel_screen.enabled` → `--set channel_screen.enabled=true` | `false` |
| Change the screen's trip threshold | `channel_screen.min_epoch_share_pct` | `50` (%) |
| **Turn ON high-offender channel dropping** | `high_offender.enabled` → `--set high_offender.enabled=true` | `false` |
| Change the offender share that triggers a drop | `high_offender.share_threshold` | `50` (%) |
| Only drop when the session is already noisy | `high_offender.min_reject_pct` | `15` (%) |
| Interpolate vs fully drop the offender | `high_offender.action` (`interpolate`/`exclude`) | `interpolate` |
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

## Turning on the high-offender toggle (your feature)

Three equivalent ways:

```bash
# one-off
xon-pipeline run --set high_offender.enabled=true

# or edit config/config.yaml:
#   high_offender:
#     enabled: true
#     share_threshold: 50.0
#     min_reject_pct: 15.0
#     action: interpolate

# or tick the box in the GUI (section "3 · Channel rejection")
```

When it fires, the master CSV records exactly which channel and its share in the
`high_offender_flagged_channels` column, so you can always see what it did.

## A note on experimenting

Because you'll be comparing settings a lot: run each configuration into its **own output
folder** so nothing overwrites, then compare the `master_everything.csv` files:

```bash
xon-pipeline run --output out_baseline
xon-pipeline run --output out_highoffender --set high_offender.enabled=true
xon-pipeline run --output out_avgref       --set artifacts.reference=average
```
