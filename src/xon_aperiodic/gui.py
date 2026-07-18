"""Native desktop GUI (Tkinter) — opens instantly, no web server, no Streamlit.

Designed for non-programmer scientists: the front-and-centre action is to DRAG your
recordings folder (or individual files) onto a drop zone. Manual path entry and a native
Browse button are there too, as secondary options. If nothing is chosen for the output,
results are saved to an ``outputs`` folder inside the program.

Runs entirely on the local machine (HIPAA-safe). Drag-and-drop uses the optional
``tkinterdnd2`` package; without it, the drop zone becomes a click-to-browse area and
everything else still works.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import webbrowser
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except Exception:                          # pragma: no cover
    _HAS_DND = False

from .config import load_config
from .logging_utils import get_logger


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def clean_path(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1]
    if s.startswith("file://"):
        from urllib.parse import unquote, urlparse
        s = unquote(urlparse(s).path)
    return os.path.expanduser(s.replace("\\ ", " ").strip().strip("'\""))


class Tooltip:
    """Hover help — the '?' equivalent."""
    def __init__(self, widget, text: str):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", background="#ffffe0", relief="solid",
                 borderwidth=1, wraplength=360, font=("Helvetica", 10)).pack(ipadx=4, ipady=2)

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def _help(parent, text: str):
    lbl = tk.Label(parent, text=" ? ", fg="#2a6f97", cursor="question_arrow", font=("Helvetica", 9, "bold"))
    Tooltip(lbl, text)
    return lbl


# --------------------------------------------------------------------------
class App:
    def __init__(self, root, config_path: Optional[str]):
        self.root = root
        self.cfg = load_config(config_path)
        self.config_path = config_path
        self.input_dir: Optional[str] = None
        self.input_files: List[str] = []
        default_out = os.environ.get("XON_DEFAULT_OUTPUT") or str(self.cfg.output_dir)
        self.output_dir = default_out
        self.log_q: "queue.Queue[str]" = queue.Queue()
        self.result = None
        self.vars = {}
        root.title("Xon Aperiodic Pipeline")
        root.geometry("880x760")
        self._build()
        self._attach_logger()
        self.root.after(150, self._poll_log)

    # ---- UI construction ----
    def _build(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.run_tab = ttk.Frame(nb); nb.add(self.run_tab, text="  Run  ")
        self.set_tab = ttk.Frame(nb); nb.add(self.set_tab, text="  Settings  ")
        self._build_run_tab()
        self._build_settings_tab()

    def _drop_zone(self, parent, title, on_drop):
        f = tk.Frame(parent, bg="#eef4f8", height=90, highlightbackground="#8fb3cc",
                     highlightthickness=2, bd=0)
        f.pack(fill="x", pady=(2, 6)); f.pack_propagate(False)
        msg = ("⬇  Drag your recordings folder (or files) here" if _HAS_DND
               else "Click a button below to choose your recordings")
        lbl = tk.Label(f, text=msg, bg="#eef4f8", fg="#33475b", font=("Helvetica", 13))
        lbl.pack(expand=True)
        if _HAS_DND:
            for w in (f, lbl):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", on_drop)
        return f

    def _build_run_tab(self):
        t = self.run_tab
        tk.Label(t, text="1.  Choose your recordings", font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(4, 0))
        self._drop_zone(t, "input", self._on_drop_input)
        row = tk.Frame(t); row.pack(fill="x")
        tk.Button(row, text="Choose folder…", command=self._choose_folder).pack(side="left")
        tk.Button(row, text="Choose files…", command=self._choose_files).pack(side="left", padx=6)
        tk.Label(row, text="or type/paste a path:").pack(side="left", padx=(12, 4))
        self.input_entry = tk.Entry(row)
        self.input_entry.pack(side="left", fill="x", expand=True)
        self.input_entry.bind("<FocusOut>", lambda e: self._set_input_from_entry())
        self.input_entry.bind("<Return>", lambda e: self._set_input_from_entry())
        self.input_status = tk.Label(t, text="No recordings chosen yet.", fg="#8a6d3b")
        self.input_status.pack(anchor="w", pady=(2, 10))

        tk.Label(t, text="2.  Where to save results", font=("Helvetica", 13, "bold")).pack(anchor="w")
        self._drop_zone(t, "output", self._on_drop_output)
        orow = tk.Frame(t); orow.pack(fill="x")
        tk.Button(orow, text="Choose output folder…", command=self._choose_output).pack(side="left")
        tk.Label(orow, text="path:").pack(side="left", padx=(12, 4))
        self.output_entry = tk.Entry(orow)
        self.output_entry.insert(0, self.output_dir)
        self.output_entry.pack(side="left", fill="x", expand=True)
        tk.Label(t, text="(Leave as-is to save inside the program's 'outputs' folder.)",
                 fg="#7a869a").pack(anchor="w", pady=(2, 10))

        self.run_btn = tk.Button(t, text="▶  Run pipeline", bg="#2a6f97", fg="white",
                                 font=("Helvetica", 14, "bold"), command=self._start_run,
                                 activebackground="#245a7d", height=2)
        self.run_btn.pack(fill="x", pady=6)

        tk.Label(t, text="Progress", font=("Helvetica", 11, "bold")).pack(anchor="w")
        self.log = tk.Text(t, height=12, wrap="word", bg="#0f1b26", fg="#d5e2ee",
                           font=("Menlo", 10), state="disabled")
        self.log.pack(fill="both", expand=True)

        self.done_row = tk.Frame(t); self.done_row.pack(fill="x", pady=6)
        self.open_report_btn = tk.Button(self.done_row, text="📄 Open cohort report",
                                         command=self._open_report, state="disabled")
        self.open_report_btn.pack(side="left")
        self.open_gallery_btn = tk.Button(self.done_row, text="🖼 Open diagnostics gallery",
                                          command=self._open_gallery, state="disabled")
        self.open_gallery_btn.pack(side="left", padx=6)
        self.open_folder_btn = tk.Button(self.done_row, text="📁 Open results folder",
                                         command=self._open_folder, state="disabled")
        self.open_folder_btn.pack(side="left")
        self.pdf_btn = tk.Button(self.done_row, text="🖨 Save report as PDF",
                                 command=self._save_pdf, state="disabled")
        self.pdf_btn.pack(side="left", padx=6)
        self.export_btn = tk.Button(self.done_row, text="📦 Export / share (.zip, PDF)",
                                    command=self._export_share, state="disabled")
        self.export_btn.pack(side="left")

    # ---- input/output selection ----
    def _split(self, data: str) -> List[str]:
        try:
            return [clean_path(p) for p in self.root.tk.splitlist(data)]
        except Exception:
            return [clean_path(data)]

    def _on_drop_input(self, event):
        paths = [p for p in self._split(event.data) if p]
        if not paths:
            return
        dirs = [p for p in paths if os.path.isdir(p)]
        files = [p for p in paths if os.path.isfile(p)]
        if len(dirs) == 1 and not files:
            self._use_folder(dirs[0])
        elif files:
            self._use_files(files)
        elif dirs:
            self._use_folder(dirs[0])

    def _on_drop_output(self, event):
        paths = [p for p in self._split(event.data) if p and os.path.isdir(p)]
        if paths:
            self.output_dir = paths[0]
            self.output_entry.delete(0, "end"); self.output_entry.insert(0, paths[0])

    def _choose_folder(self):
        d = filedialog.askdirectory(title="Select the folder with your recordings")
        if d:
            self._use_folder(d)

    def _choose_files(self):
        fs = filedialog.askopenfilenames(title="Select your recording files")
        if fs:
            self._use_files(list(fs))

    def _choose_output(self):
        d = filedialog.askdirectory(title="Select where to save results")
        if d:
            self.output_dir = d
            self.output_entry.delete(0, "end"); self.output_entry.insert(0, d)

    def _set_input_from_entry(self):
        p = clean_path(self.input_entry.get())
        if not p:
            return
        if os.path.isdir(p):
            self._use_folder(p)
        elif os.path.isfile(p):
            self._use_files([p])

    def _use_folder(self, d: str):
        self.input_dir, self.input_files = d, []
        self.input_entry.delete(0, "end"); self.input_entry.insert(0, d)
        self.input_status.config(text=f"✓ Folder selected: {d}", fg="#2a7d4f")

    def _use_files(self, files: List[str]):
        self.input_files, self.input_dir = files, None
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, f"{len(files)} file(s) selected")
        self.input_status.config(text=f"✓ {len(files)} file(s) selected", fg="#2a7d4f")

    # ---- settings tab ----
    def _build_settings_tab(self):
        canvas = tk.Canvas(self.set_tab, highlightthickness=0)
        sb = ttk.Scrollbar(self.set_tab, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        A = self.cfg.section("artifacts"); ho = self.cfg.section("high_offender")
        er = self.cfg.section("exponent_rejection"); an = self.cfg.section("analysis")
        fl = self.cfg.section("filter"); ep = self.cfg.section("epoch"); cr = self.cfg.section("crop")
        xd = self.cfg.section("xdf"); fr = self.cfg.get("fooof", "freq_range", [1, 40])

        def group(title):
            lf = ttk.LabelFrame(inner, text=title)
            lf.pack(fill="x", padx=10, pady=8, ipady=4)
            return lf

        def row(parent, label, help_text):
            r = tk.Frame(parent); r.pack(fill="x", padx=8, pady=3)
            tk.Label(r, text=label, width=26, anchor="w").pack(side="left")
            _help(r, help_text).pack(side="right")
            return r

        def combo(parent, key, label, options, current, help_text):
            r = row(parent, label, help_text)
            v = tk.StringVar(value=str(current)); self.vars[key] = ("str", v)
            ttk.Combobox(r, textvariable=v, values=options, state="readonly", width=18).pack(side="left")

        def check(parent, key, label, current, help_text):
            r = row(parent, label, help_text)
            v = tk.BooleanVar(value=bool(current)); self.vars[key] = ("bool", v)
            tk.Checkbutton(r, variable=v).pack(side="left")

        def num(parent, key, label, current, help_text):
            r = row(parent, label, help_text)
            v = tk.StringVar(value=str(current if current is not None else "")); self.vars[key] = ("num", v)
            tk.Entry(r, textvariable=v, width=12).pack(side="left")

        def text(parent, key, label, current, help_text):
            r = row(parent, label, help_text)
            v = tk.StringVar(value=str(current if current is not None else "")); self.vars[key] = ("text", v)
            tk.Entry(r, textvariable=v, width=22).pack(side="left")

        g = group("Basics")
        combo(g, "performance.n_jobs", "Parallel workers", ["auto", "1", "2", "4", "6", "8"],
              self.cfg.get("performance", "n_jobs", "auto"),
              "How many recordings to process at once. 'auto' is safe; more is faster, more memory.")
        text(g, "io.file_glob", "File pattern", self.cfg.get("io", "file_glob", "*"),
             "Which files count as recordings. '*' matches everything (Xon files often have no "
             "extension); non-data files are skipped automatically.")
        check(g, "io.recursive", "Search sub-folders", self.cfg.get("io", "recursive", True),
              "Also look inside folders within the recordings folder.")

        g = group("Artifact rejection")
        cur_ref = "ear (device A2 — keep)" if self.cfg.reference is None else str(self.cfg.reference)
        combo(g, "artifacts.reference", "Reference", ["ear (device A2 — keep)", "average", "Cz"],
              cur_ref, "How the EEG is referenced. The Xon papers keep the ear-clip (A2) reference.")
        check(g, "artifacts.run_ica", "Run ICA", A.get("run_ica", False),
              "Off by default — underpowered at 7 channels; epoch rejection is the safety net.")
        num(g, "artifacts.amplitude_threshold_uv", "Amplitude reject (µV)",
            A.get("amplitude_threshold_uv", 100.0), "Drop epochs whose peak-to-peak exceeds this.")
        num(g, "artifacts.gradient_threshold_uv_per_ms", "Gradient reject (µV/ms)",
            A.get("gradient_threshold_uv_per_ms", 10.0), "Drop epochs with a steeper sample-to-sample jump.")
        num(g, "artifacts.variance_zscore_threshold", "Variance z", A.get("variance_zscore_threshold", 3.0),
            "Reject epochs that are variance outliers (blank to disable).")
        num(g, "artifacts.muscle_zscore_threshold", "Muscle z", A.get("muscle_zscore_threshold", 3.0),
            "Reject epochs with excess high-frequency (muscle) power (blank to disable).")

        g = group("Channel rejection")
        check(g, "exponent_rejection.enabled", "Reject flat-exponent channels", er.get("enabled", True),
              "Drop a channel whose final exponent is implausibly flat (muscle). Mentor-endorsed.")
        num(g, "exponent_rejection.threshold", "Exponent threshold", er.get("threshold", 0.5),
            "Channels below this exponent are treated as artifact.")
        check(g, "high_offender.enabled", "High-offender channel rejection", ho.get("enabled", False),
              "If one channel causes most of a session's rejections, drop/interpolate just it.")
        num(g, "high_offender.share_threshold", "Offender share (%)", ho.get("share_threshold", 50.0),
            "A channel above this share of rejected epochs is the culprit.")
        num(g, "high_offender.min_reject_pct", "Only if rejection ≥ (%)", ho.get("min_reject_pct", 15.0),
            "Safety gate: only act when the session is already noisy.")
        combo(g, "high_offender.action", "Action", ["interpolate", "exclude"],
              ho.get("action", "interpolate"), "Rebuild from neighbours, or drop entirely.")

        g = group("Spectrum (FOOOF)")
        num(g, "fooof.freq_range.0", "Fit low (Hz)", fr[0], "Lower bound of the 1/f fit band (Donoghue 2020).")
        num(g, "fooof.freq_range.1", "Fit high (Hz)", fr[1], "Upper bound of the fit band.")
        combo(g, "fooof.aperiodic_mode", "Aperiodic mode", ["fixed", "knee"],
              self.cfg.fooof_settings.get("aperiodic_mode", "fixed"), "'fixed' = straight line; 'knee' = allow a bend.")

        g = group("Advanced — filtering, epoching, montage, analyses")
        num(g, "filter.high_pass_hz", "High-pass (Hz)", fl.get("high_pass_hz", 0.1), "Removes slow drift.")
        num(g, "filter.notch_freq_hz", "Notch (Hz, blank = off)", fl.get("notch_freq_hz", 60.0), "Mains hum: 60 US / 50 EU.")
        num(g, "crop.start_sec", "Crop start (s, blank = none)", cr.get("start_sec"), "Trim setup time at the start.")
        num(g, "crop.stop_sec", "Crop stop (s, blank = none)", cr.get("stop_sec"), "Trim after this time.")
        num(g, "epoch.length_sec", "Epoch length (s)", ep.get("length_sec", 1.0), "Xon papers: 1 s.")
        num(g, "epoch.overlap_sec", "Epoch overlap (s)", ep.get("overlap_sec", 0.1), "Xon papers: 0.1 s.")
        check(g, "artifacts.detect_bad_channels", "Detect bad channels", A.get("detect_bad_channels", True), "Flag dead/noisy channels.")
        check(g, "artifacts.interpolate_bad_channels", "Interpolate bad channels", A.get("interpolate_bad_channels", True), "Rebuild flagged channels; excluded from the average.")
        combo(g, "artifacts.interpolation_method", "Interpolation", ["average", "spline"], A.get("interpolation_method", "average"), "Average of good channels (robust at 7 ch) or spherical spline.")
        text(g, "montage.name", "Montage", self.cfg.montage_name or "standard_1020", "Electrode-position template; 'none' disables.")
        combo(g, "xdf.data_units", "Data units", ["uV", "mV", "V"], xd.get("data_units", "uV"), "Units the device stored EEG in.")
        check(g, "analysis.block_analysis", "Block analysis (over time)", an.get("block_analysis", True), "Fit each 5-min block to see drift.")
        check(g, "analysis.reliability_analysis", "Reliability vs recording length", an.get("reliability_analysis", True), "The 'how few minutes are enough' analysis.")

    # ---- assemble config from settings ----
    def _apply_settings(self):
        cfg = self.cfg
        def setpath(path, value):
            keys = path.split("."); node = cfg.data
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = value
        for key, (kind, var) in self.vars.items():
            raw = var.get()
            if kind == "bool":
                val = bool(raw)
            elif kind == "num":
                val = None if str(raw).strip() == "" else float(raw)
            else:
                val = raw
            if key == "artifacts.reference":
                val = None if str(raw).startswith("ear") else raw
            if key.startswith("fooof.freq_range."):
                idx = int(key.split(".")[-1])
                fr = list(cfg.get("fooof", "freq_range", [1, 40]))
                fr[idx] = float(raw); cfg.data["fooof"]["freq_range"] = fr
                continue
            if key == "montage.name":
                cfg.data.setdefault("montage", {})["name"] = raw
                continue
            setpath(key, val)
        cfg.data["io"]["input_dir"] = self.input_dir or cfg.get("io", "input_dir")
        cfg.data["io"]["output_dir"] = clean_path(self.output_entry.get()) or self.output_dir
        cfg.validate()
        return cfg

    # ---- run ----
    def _start_run(self):
        if not self.input_dir and not self.input_files:
            messagebox.showwarning("No recordings", "Please choose a recordings folder or files first.")
            return
        try:
            cfg = self._apply_settings()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc)); return

        # If the output folder already has results, ask what to do (unless it's a new folder).
        from xon_aperiodic.batch import output_has_results, timestamped_sibling
        if output_has_results(cfg.output_dir):
            choice = messagebox.askyesnocancel(
                "This folder already has results",
                f"'{cfg.output_dir}' already contains results from a previous run.\n\n"
                "•  Yes  = overwrite them\n"
                "•  No   = keep them and save this run as a new copy\n"
                "•  Cancel = don't run")
            if choice is None:
                return  # cancel
            if choice is False:  # new copy
                new = str(timestamped_sibling(cfg.output_dir))
                cfg.data["io"]["output_dir"] = new
                self.output_entry.delete(0, "end"); self.output_entry.insert(0, new)
                self._log_write(f"Saving this run to a new copy: {new}")

        self.run_btn.config(state="disabled", text="Running…")
        for b in (self.open_report_btn, self.open_gallery_btn, self.open_folder_btn):
            b.config(state="disabled")
        self._log_clear()
        files = [Path(f) for f in self.input_files] if self.input_files else None
        threading.Thread(target=self._run_worker, args=(cfg, files), daemon=True).start()

    def _run_worker(self, cfg, files):
        from .batch import run_batch
        try:
            self.result = run_batch(cfg=cfg, input_files=files)
            self.log_q.put("__DONE__")
        except Exception as exc:
            self.log_q.put(f"\nERROR: {exc}")
            self.log_q.put("__FAILED__")

    # ---- logging bridge ----
    def _attach_logger(self):
        app = self

        class H(logging.Handler):
            def __init__(self):
                super().__init__(); self._keep = True
            def emit(self, record):
                app.log_q.put(self.format(record))
        h = H(); h.setFormatter(logging.Formatter("%(message)s"))
        lg = get_logger(); lg.setLevel(logging.INFO); lg.addHandler(h)

    def _poll_log(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                if msg == "__DONE__":
                    self._finish(ok=True)
                elif msg == "__FAILED__":
                    self._finish(ok=False)
                else:
                    self._log_write(msg)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_log)

    def _finish(self, ok: bool):
        self.run_btn.config(state="normal", text="▶  Run pipeline")
        if ok:
            self._log_write("\n✓ Done.")
            for b in (self.open_report_btn, self.open_gallery_btn, self.open_folder_btn,
                      self.pdf_btn, self.export_btn):
                b.config(state="normal")
            # auto-open the report
            self._open_report()
        else:
            messagebox.showerror("Pipeline failed", "See the progress log for details.")

    def _log_clear(self):
        self.log.config(state="normal"); self.log.delete("1.0", "end"); self.log.config(state="disabled")

    def _log_write(self, msg: str):
        self.log.config(state="normal"); self.log.insert("end", msg + "\n")
        self.log.see("end"); self.log.config(state="disabled")

    # ---- open results ----
    def _out(self, name):
        outputs = self.result or {}
        p = outputs.get(name)
        if p and Path(p).exists():
            return p
        base = Path(self.output_entry.get() or self.output_dir)
        cand = base / ({"cohort_report": "cohort_report.html", "gallery": "gallery.html"}.get(name, ""))
        return str(cand) if cand.exists() else None

    def _open_report(self):
        p = self._out("cohort_report")
        if p:
            webbrowser.open(Path(p).as_uri())

    def _open_gallery(self):
        p = self._out("gallery")
        if p:
            webbrowser.open(Path(p).as_uri())

    def _open_folder(self):
        base = self.output_entry.get() or self.output_dir
        if os.path.isdir(base):
            if os.name == "nt":
                os.startfile(base)              # noqa: S606
            else:
                import subprocess
                subprocess.run(["open" if os.uname().sysname == "Darwin" else "xdg-open", base])

    def _save_pdf(self):
        """Open the report in the browser and prompt Save-as-PDF (works on any machine)."""
        base = Path(self.output_entry.get() or self.output_dir)
        standalone = base / "cohort_report_standalone.html"
        target = standalone if standalone.exists() else Path(self._out("cohort_report") or "")
        if target and Path(target).exists():
            webbrowser.open(Path(target).as_uri())
            shortcut = "⌘P" if sys.platform == "darwin" else "Ctrl+P"
            messagebox.showinfo("Save as PDF",
                                f"The report opened in your browser.\n\nPress {shortcut}, then choose "
                                "'Save as PDF' as the destination. This gives a clean, shareable PDF.")

    def _export_share(self):
        """Create figures.pdf, single-file HTMLs, and a shareable ZIP, then open the folder."""
        from xon_aperiodic.reporting import export as EX
        base = self.output_entry.get() or self.output_dir
        try:
            paths = EX.export_all(base)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc)); return
        made = "\n".join(f"• {Path(v).name}" for v in paths.values()) or "(nothing to export)"
        messagebox.showinfo("Exported for sharing",
                            f"Created in the results folder:\n\n{made}\n\n"
                            "The .zip bundles everything; figures.pdf is ready for slides; the "
                            "*_standalone.html files are single portable files you can email.")
        self._open_folder()


def main(config_path: Optional[str] = None) -> int:
    root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
    App(root, config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
