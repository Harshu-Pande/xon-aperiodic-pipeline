"""Offline GUI (Streamlit) with a native folder picker and full settings.

Runs entirely on the local machine - Streamlit serves to 127.0.0.1, nothing is
uploaded anywhere, so it is HIPAA-safe for real Xon data. Launch with:
    xon-pipeline gui      (or double-click the Start Here launcher)

Design goals: a scientist should be able to run and fully configure the pipeline
without ever seeing code or a file path. A native "Browse" button opens the real
macOS/Windows folder chooser; typed paths are cleaned automatically; every setting
in config.yaml is available, with basics up top and the rest under "Advanced".
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import streamlit as st
except ImportError:                       # pragma: no cover
    print("This module requires streamlit:  pip install streamlit")
    sys.exit(1)

import pandas as pd

from xon_aperiodic.config import load_config, default_config_path
from xon_aperiodic.batch import run_batch, find_xdf_files


# --------------------------------------------------------------------------
# helpers: native folder picker + robust path cleaning
# --------------------------------------------------------------------------
def pick_folder(prompt: str = "Select a folder") -> str | None:
    """Open the operating system's native folder chooser and return the path."""
    try:
        if sys.platform == "darwin":
            script = f'POSIX path of (choose folder with prompt "{prompt}")'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
            return r.stdout.strip() or None
        if sys.platform.startswith("win"):
            ps = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$f=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "if($f.ShowDialog() -eq 'OK'){Write-Output $f.SelectedPath}")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=120)
            return r.stdout.strip() or None
        r = subprocess.run(["zenity", "--file-selection", "--directory", "--title", prompt],
                           capture_output=True, text=True, timeout=120)
        return r.stdout.strip() or None
    except Exception:
        return None


def clean_path(s: str) -> str:
    """Forgive the many ways a pasted path arrives: surrounding quotes, file:// URLs,
    backslash-escaped spaces, ~, and stray whitespace."""
    if not s:
        return ""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":     # wrapped in quotes
        s = s[1:-1]
    if s.startswith("file://"):
        s = unquote(urlparse(s).path)
    s = s.replace("\\ ", " ").strip().strip("'\"")           # unescape spaces
    s = os.path.expanduser(s)
    return s


def _folder_field(label: str, key: str, default: str, prompt: str, help_text: str) -> str:
    """A text box + native Browse button that stay in sync."""
    val_key = f"{key}_val"
    if val_key not in st.session_state:
        st.session_state[val_key] = default
    c1, c2 = st.columns([4, 1])
    if c2.button("📁 Browse", key=f"{key}_btn"):
        picked = pick_folder(prompt)
        if picked:
            st.session_state[val_key] = picked
    typed = c1.text_input(label, value=st.session_state[val_key], key=f"{key}_box", help=help_text)
    st.session_state[val_key] = typed
    return clean_path(typed)


def _get_config_arg() -> str | None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    args, _ = parser.parse_known_args()
    return args.config


# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Xon Aperiodic Pipeline", page_icon="🧠", layout="wide")
    st.title("🧠 Xon Aperiodic Pipeline")
    st.caption("Runs entirely on this computer — no data leaves the machine.")

    cfg_path = _get_config_arg() or str(default_config_path())
    cfg = load_config(cfg_path)
    A = cfg.section("artifacts")
    er = cfg.section("exponent_rejection"); an = cfg.section("analysis")
    fl = cfg.section("filter"); ep = cfg.section("epoch"); cr = cfg.section("crop")
    md = cfg.section("metadata"); xd = cfg.section("xdf"); stt = cfg.section("stats")
    fr = cfg.get("fooof", "freq_range", [1, 40])
    default_input = os.environ.get("XON_DEFAULT_INPUT") or str(cfg.input_dir)
    default_output = os.environ.get("XON_DEFAULT_OUTPUT") or str(cfg.output_dir)

    st.markdown("#### 1. Choose your recordings folder, then press Run. Everything else has "
                "sensible defaults.")

    # ---------------- DATA ----------------
    input_dir = _folder_field("Folder of recordings", "input", default_input,
                              "Select the folder that holds your recordings",
                              "The folder containing your .xdf recordings. Use Browse to pick it — "
                              "no need to type or copy a path.")
    output_dir = _folder_field("Where to save results", "output", default_output,
                               "Select where results should be saved",
                               "Results, figures and reports are written here.")
    with st.expander("File matching & speed"):
        pattern = st.text_input("File pattern", value=str(cfg.get("io", "file_glob", "*.xdf")),
                                help="Which files count as recordings. Use * if your files have no "
                                     ".xdf extension. Hidden files are always skipped.")
        recursive = st.checkbox("Search sub-folders", value=bool(cfg.get("io", "recursive", True)),
                                help="Also look inside folders within the recordings folder.")
        n_jobs = st.selectbox("Parallel workers", ["auto", "1", "2", "4", "6", "8"], index=0,
                              help="How many recordings to process at once. 'auto' is a safe choice; "
                                   "more is faster but uses more memory.")

    # ---------------- COMMON SETTINGS ----------------
    st.markdown("#### 2. Common settings")
    col1, col2 = st.columns(2)
    with col1:
        reference = st.selectbox("Reference", ["ear (device A2 — keep)", "average", "Cz"], index=0,
                                 help="How the EEG is referenced. The Xon papers keep the device's "
                                      "ear-clip (A2) reference; 'average' re-references to the mean.")
        run_ica = st.checkbox("Run ICA", value=bool(A.get("run_ica", False)),
                              help="Independent Component Analysis. Off by default — it is "
                                   "underpowered with only 7 channels; epoch rejection is the safety net.")
        exp_reject = st.checkbox("Reject flat-exponent channels", value=bool(er.get("enabled", True)),
                                 help="Drop a channel whose final exponent is implausibly flat "
                                      "(muscle-contaminated). Mentor-endorsed.")
        exp_thr = st.number_input("Exponent reject threshold", value=float(er.get("threshold", 0.5)),
                                  step=0.1, help="Channels below this exponent are treated as artifact.")
    with col2:
        f_lo = st.number_input("FOOOF fit — low (Hz)", value=float(fr[0]), step=1.0,
                               help="Lower bound of the 1/f fitting band. 1–40 Hz keeps the fit out "
                                    "of the muscle band (Donoghue et al. 2020).")
        f_hi = st.number_input("FOOOF fit — high (Hz)", value=float(fr[1]), step=1.0,
                               help="Upper bound of the fitting band.")
        ap_mode = st.selectbox("Aperiodic mode", ["fixed", "knee"],
                               index=0 if cfg.fooof_settings.get("aperiodic_mode") == "fixed" else 1,
                               help="'fixed' = straight 1/f line; 'knee' allows a bend at low "
                                    "frequencies.")


    # ---------------- ADVANCED ----------------
    with st.expander("⚙️ Advanced settings (filtering, epoching, thresholds, montage, metadata)"):
        st.markdown("**Filtering**")
        a1, a2 = st.columns(2)
        hp = a1.number_input("High-pass (Hz)", value=float(fl.get("high_pass_hz") or 0.1), step=0.1,
                             help="Removes slow drift. 0.1 Hz matches the Xon validation protocol.")
        notch = a2.number_input("Notch (Hz, 0 = off)", value=float(fl.get("notch_freq_hz") or 0.0),
                                step=10.0, help="Removes mains hum: 60 in the US, 50 in Europe.")
        st.markdown("**Cropping** (trim setup time; 0 = don't crop that end)")
        c1, c2, c3 = st.columns(3)
        crop_start = c1.number_input("Start (s)", value=float(cr.get("start_sec") or 0.0), step=10.0)
        crop_stop = c2.number_input("Stop (s, 0 = end)", value=float(cr.get("stop_sec") or 0.0), step=10.0)
        exp_dur = c3.number_input("Expected length (min, 0 = skip)",
                                  value=float(cr.get("expected_duration_min") or 0.0), step=1.0)
        st.markdown("**Epoching** (Xon papers: 1 s epochs, 0.1 s overlap)")
        e1, e2 = st.columns(2)
        ep_len = e1.number_input("Epoch length (s)", value=float(ep.get("length_sec", 1.0)), step=0.5)
        ep_ov = e2.number_input("Epoch overlap (s)", value=float(ep.get("overlap_sec", 0.1)), step=0.05)
        st.markdown("**Artifact thresholds** (Xon papers: amplitude 100 µV, gradient 10 µV/ms)")
        t1, t2, t3 = st.columns(3)
        amp_uv = t1.number_input("Amplitude (µV)", value=float(A.get("amplitude_threshold_uv", 100.0)), step=10.0)
        grad = t2.number_input("Gradient (µV/ms)", value=float(A.get("gradient_threshold_uv_per_ms") or 10.0), step=1.0)
        flat_uv = t3.number_input("Flat (µV)", value=float(A.get("flat_threshold_uv", 1.0)), step=0.5)
        z1, z2, z3 = st.columns(3)
        var_z = z1.number_input("Variance z", value=float(A.get("variance_zscore_threshold") or 3.0), step=0.5)
        mus_z = z2.number_input("Muscle z", value=float(A.get("muscle_zscore_threshold") or 3.0), step=0.5)
        mus_hf = z3.number_input("Muscle band (Hz)", value=float(A.get("muscle_hf_hz", 30.0)), step=5.0)
        st.markdown("**Bad channels & montage**")
        b1, b2 = st.columns(2)
        detect_bad = b1.checkbox("Detect bad channels", value=bool(A.get("detect_bad_channels", True)))
        interp = b2.checkbox("Interpolate bad channels", value=bool(A.get("interpolate_bad_channels", True)))
        bad_z = b1.number_input("Bad-channel z", value=float(A.get("bad_channel_zscore", 3.0)), step=0.5)
        interp_method = b2.selectbox("Interpolation", ["average", "spline"],
                                     index=0 if A.get("interpolation_method") == "average" else 1)
        montage = st.text_input("Montage", value=str(cfg.montage_name or "standard_1020"),
                                help="Electrode-position template. 'none' disables it.")
        st.markdown("**Within-recording analyses**")
        n1, n2 = st.columns(2)
        block_on = n1.checkbox("Block analysis (over time)", value=bool(an.get("block_analysis", True)))
        rel_on = n2.checkbox("Reliability vs recording length", value=bool(an.get("reliability_analysis", True)))
        st.markdown("**Data units & metadata parsing**")
        units = st.selectbox("Data units", ["uV", "mV", "V"],
                             index=["uV", "mV", "V"].index(str(xd.get("data_units", "uV"))),
                             help="Units the device stored EEG in. Usually microvolts.")
        pat = md.get("patterns", {})
        p1, p2, p3 = st.columns(3)
        pat_p = p1.text_input("Participant pattern", value=str(pat.get("participant", "")),
                              help="Regular expression to read the participant from the filename.")
        pat_s = p2.text_input("Session pattern", value=str(pat.get("session", "")))
        pat_c = p3.text_input("Condition pattern", value=str(pat.get("condition", "")))
        manifest = st.text_input("Manifest CSV (optional)", value=str(md.get("manifest") or ""),
                                 help="A CSV mapping each file to participant/session/condition, if "
                                      "filenames don't carry that info. Overrides the patterns above.")

    run_stats = st.checkbox("Run cohort statistics + report", value=True)
    st.caption(f"Advanced defaults live in `{cfg_path}`. Nothing here changes that file.")

    # ---------------- apply overrides ----------------
    cfg.data["io"].update(dict(input_dir=input_dir, output_dir=output_dir,
                               file_glob=pattern, recursive=recursive))
    cfg.data["performance"]["n_jobs"] = n_jobs
    cfg.data["artifacts"]["reference"] = (None if reference.startswith("ear")
                                          else ("average" if reference == "average" else "Cz"))
    cfg.data["artifacts"].update(dict(
        run_ica=run_ica, amplitude_threshold_uv=amp_uv,
        gradient_threshold_uv_per_ms=(grad if grad > 0 else None), flat_threshold_uv=flat_uv,
        variance_zscore_threshold=var_z, muscle_zscore_threshold=mus_z, muscle_hf_hz=mus_hf,
        detect_bad_channels=detect_bad, interpolate_bad_channels=interp,
        bad_channel_zscore=bad_z, interpolation_method=interp_method))
    cfg.data["exponent_rejection"].update(dict(enabled=exp_reject, threshold=exp_thr))
    cfg.data["fooof"].update(dict(freq_range=[f_lo, f_hi], aperiodic_mode=ap_mode))
    cfg.data["filter"].update(dict(high_pass_hz=(hp if hp > 0 else None),
                                   notch_freq_hz=(notch if notch > 0 else None)))
    cfg.data["crop"].update(dict(start_sec=(crop_start if crop_start > 0 else None),
                                 stop_sec=(crop_stop if crop_stop > 0 else None),
                                 expected_duration_min=(exp_dur if exp_dur > 0 else None)))
    cfg.data["epoch"].update(dict(length_sec=ep_len, overlap_sec=ep_ov))
    cfg.data["analysis"].update(dict(block_analysis=block_on, reliability_analysis=rel_on))
    cfg.data["xdf"]["data_units"] = units
    cfg.data["montage"]["name"] = montage
    cfg.data["metadata"]["patterns"] = dict(participant=pat_p or None, session=pat_s or None,
                                            condition=pat_c or None)
    cfg.data["metadata"]["manifest"] = manifest or None
    try:
        cfg.validate()
    except Exception as exc:
        st.error(f"Invalid settings: {exc}")
        st.stop()

    # ---------------- preview + run ----------------
    try:
        files = find_xdf_files(cfg.input_dir, pattern=pattern, recursive=recursive)
        st.success(f"Found {len(files)} recording(s) in `{cfg.input_dir}`.")
        with st.expander("Files that will be processed"):
            st.write([f.name for f in files])
    except Exception as exc:
        st.warning(f"No recordings found yet — check the folder above. ({exc})")
        files = []

    if st.button("▶ Run pipeline", type="primary", disabled=not files):
        with st.spinner("Processing… you'll see results here when it finishes."):
            try:
                outputs = run_batch(cfg=cfg, run_stats=run_stats)
            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")
                st.stop()
        st.balloons()
        st.success("Done!")
        _show_results(outputs, cfg)


def _show_results(outputs: dict, cfg) -> None:
    master_csv = outputs.get("master_csv")
    if master_csv and Path(master_csv).exists():
        df = pd.read_csv(master_csv)
        st.subheader("Results (one row per recording)")
        lead = [c for c in ["subject_id", "participant", "session", "condition",
                            "AVERAGE_exponent", "AVERAGE_r_squared", "pct_epochs_rejected",
                            "screened_channels", "status"] if c in df.columns]
        st.dataframe(df[lead] if lead else df, use_container_width=True)
        st.download_button("Download full results (CSV)", df.to_csv(index=False),
                           file_name="master_everything.csv")
    report = outputs.get("cohort_report")
    if report and Path(report).exists():
        st.subheader("Cohort report")
        st.components.v1.html(Path(report).read_text(), height=800, scrolling=True)
    figs = [v for k, v in outputs.items() if k.startswith("fig_") and Path(str(v)).exists()]
    if figs:
        st.subheader("Figures")
        cols = st.columns(2)
        for i, fig in enumerate(figs):
            cols[i % 2].image(fig, use_container_width=True)
    st.info(f"All files were written to: `{cfg.output_dir}`")


main()
