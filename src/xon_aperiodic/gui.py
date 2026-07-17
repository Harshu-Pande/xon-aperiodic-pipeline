"""Offline drag-and-drop GUI (Streamlit) with point-and-click settings.

Runs entirely on the local machine - Streamlit serves to 127.0.0.1, nothing is
uploaded anywhere, so it is HIPAA-safe for real Xon patient data. Launch with:
    xon-pipeline gui            (or ./run.sh gui)

Every knob you're likely to tinker with is a control in the sidebar; anything you set
here overrides config/config.yaml for that run only (the file itself is never changed).
Advanced / rarely-touched settings still live in config/config.yaml.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import streamlit as st
except ImportError:                       # pragma: no cover
    print("This module requires streamlit:  pip install streamlit")
    sys.exit(1)

import pandas as pd

from xon_aperiodic.config import load_config, default_config_path
from xon_aperiodic.batch import run_batch, find_xdf_files


def _get_config_arg() -> str | None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    args, _ = parser.parse_known_args()
    return args.config


def main() -> None:
    st.set_page_config(page_title="Xon Aperiodic Pipeline", page_icon="🧠", layout="wide")
    st.title("🧠 Xon Aperiodic Pipeline")
    st.caption("Runs fully offline on this computer — no data leaves the machine (HIPAA-safe). "
               "Set the folder and options, then press Run.")

    cfg_path = _get_config_arg() or str(default_config_path())
    cfg = load_config(cfg_path)
    A = cfg.section("artifacts")
    ho = cfg.section("high_offender")
    er = cfg.section("exponent_rejection")
    fr = cfg.get("fooof", "freq_range", [1, 40])

    with st.sidebar:
        st.header("1 · Data")
        input_dir = st.text_input("Folder of recordings", value=str(cfg.input_dir))
        output_dir = st.text_input("Output folder", value=str(cfg.output_dir))
        pattern = st.text_input("File pattern", value=str(cfg.get("io", "file_glob", "*.xdf")),
                                help="Use * if your files have no .xdf extension.")
        recursive = st.checkbox("Search sub-folders", value=bool(cfg.get("io", "recursive", True)))

        st.header("2 · Artifact rejection")
        reference = st.selectbox("Reference", ["ear (device A2, keep)", "average", "Cz"],
                                 index=0, help="How the EEG is referenced.")
        run_ica = st.checkbox("Run ICA (off by default; weak at 7 ch)", value=bool(A.get("run_ica", False)))
        amp_uv = st.number_input("Amplitude reject (µV)", value=float(A.get("amplitude_threshold_uv", 100.0)),
                                 step=10.0)
        grad = st.number_input("Gradient reject (µV/ms)",
                               value=float(A.get("gradient_threshold_uv_per_ms", 10.0) or 10.0), step=1.0)

        st.header("3 · Channel rejection")
        exp_reject = st.checkbox("Reject channels with flat exponent",
                                 value=bool(er.get("enabled", True)))
        exp_thr = st.number_input("Exponent reject threshold", value=float(er.get("threshold", 0.5)),
                                  step=0.1, help="Channels with a final exponent below this are dropped.")
        st.markdown("**High-offender channel rejection** (experimental)")
        ho_on = st.checkbox("Drop a channel that causes most rejections",
                            value=bool(ho.get("enabled", False)),
                            help="If one electrode causes more than the share below of a session's "
                                 "rejected epochs, drop/interpolate just that channel.")
        ho_share = st.slider("Rejection-share threshold (%)", 10, 100,
                             int(ho.get("share_threshold", 50)), disabled=not ho_on)
        ho_min = st.slider("Only if overall rejection ≥ (%)", 0, 50,
                           int(ho.get("min_reject_pct", 15)), disabled=not ho_on)
        ho_action = st.selectbox("Action", ["interpolate", "exclude"],
                                 index=0 if ho.get("action", "interpolate") == "interpolate" else 1,
                                 disabled=not ho_on)

        st.header("4 · Spectrum (FOOOF)")
        c1, c2 = st.columns(2)
        f_lo = c1.number_input("Fit low (Hz)", value=float(fr[0]), step=1.0)
        f_hi = c2.number_input("Fit high (Hz)", value=float(fr[1]), step=1.0)
        ap_mode = st.selectbox("Aperiodic mode", ["fixed", "knee"],
                               index=0 if cfg.fooof_settings.get("aperiodic_mode") == "fixed" else 1)

        run_stats = st.checkbox("Run cohort statistics + report", value=True)
        st.caption(f"Everything else lives in `{cfg_path}`.")

    # apply overrides to the config for this run
    cfg.data["io"].update(dict(input_dir=input_dir, output_dir=output_dir,
                               file_glob=pattern, recursive=recursive))
    cfg.data["artifacts"]["reference"] = (None if reference.startswith("ear")
                                          else ("average" if reference == "average" else "Cz"))
    cfg.data["artifacts"]["run_ica"] = run_ica
    cfg.data["artifacts"]["amplitude_threshold_uv"] = amp_uv
    cfg.data["artifacts"]["gradient_threshold_uv_per_ms"] = grad
    cfg.data["exponent_rejection"].update(dict(enabled=exp_reject, threshold=exp_thr))
    cfg.data["high_offender"].update(dict(enabled=ho_on, share_threshold=float(ho_share),
                                          min_reject_pct=float(ho_min), action=ho_action))
    cfg.data["fooof"]["freq_range"] = [f_lo, f_hi]
    cfg.data["fooof"]["aperiodic_mode"] = ap_mode
    try:
        cfg.validate()
    except Exception as exc:
        st.error(f"Invalid settings: {exc}")
        st.stop()

    try:
        files = find_xdf_files(cfg.input_dir, pattern=pattern, recursive=recursive)
        st.success(f"Found {len(files)} recording(s) in `{cfg.input_dir}`.")
        with st.expander("Files that will be processed"):
            st.write([f.name for f in files])
    except Exception as exc:
        st.warning(f"No files found yet: {exc}")
        files = []

    if st.button("▶ Run pipeline", type="primary", disabled=not files):
        with st.spinner("Processing… this can take a few minutes for a full cohort."):
            try:
                outputs = run_batch(cfg=cfg, run_stats=run_stats)
            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")
                st.stop()
        st.balloons()
        st.success("Done!")

        master_csv = outputs.get("master_csv")
        if master_csv and Path(master_csv).exists():
            df = pd.read_csv(master_csv)
            st.subheader("Master results (one row per recording)")
            lead = [c for c in ["subject_id", "participant", "session", "condition",
                                "AVERAGE_exponent", "AVERAGE_r_squared", "pct_epochs_rejected",
                                "minutes_to_stability", "high_offender_flagged_channels", "status"]
                    if c in df.columns]
            st.dataframe(df[lead] if lead else df, use_container_width=True)
            st.download_button("Download master_everything.csv", df.to_csv(index=False),
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
        st.info(f"All files written to: `{cfg.output_dir}`")


main()
