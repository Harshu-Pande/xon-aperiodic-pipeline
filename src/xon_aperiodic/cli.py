"""Command-line interface:  xon-pipeline <command>

Commands
  run       Process a folder (or one file) end-to-end. This is the usual command.
  streams   List the streams in an .xdf file (use if auto stream-detection guesses wrong).
  gui       Launch the offline drag-and-drop GUI (needs `pip install streamlit`).
  config    Print the resolved configuration (after defaults + overrides).

Everything is driven by config/config.yaml; --set lets you override any single key
from the command line without editing the file, e.g.
    xon-pipeline run --set artifacts.reference=average --set fooof.freq_range=[2,45]
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from .config import Config, load_config, default_config_path
from .logging_utils import setup_logging, info


def _coerce(value: str) -> Any:
    """Turn a CLI string into a Python value (int/float/bool/list/None/str)."""
    low = value.strip().lower()
    if low in {"none", "null", "~"}:
        return None
    if low in {"true", "yes"}:
        return True
    if low in {"false", "no"}:
        return False
    try:
        return ast.literal_eval(value)
    except Exception:
        return value


def _apply_overrides(cfg: Config, sets: Optional[List[str]]) -> Config:
    for item in sets or []:
        if "=" not in item:
            raise SystemExit(f"--set expects section.key=value, got {item!r}")
        dotted, raw = item.split("=", 1)
        keys = dotted.strip().split(".")
        node = cfg.data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = _coerce(raw)
    cfg.validate()
    return cfg


def _load(args) -> Config:
    cfg = load_config(args.config)
    _apply_overrides(cfg, getattr(args, "set", None))
    if getattr(args, "input_dir", None):
        cfg.data.setdefault("io", {})["input_dir"] = args.input_dir
    if getattr(args, "output", None):
        cfg.data.setdefault("io", {})["output_dir"] = args.output
    if getattr(args, "pattern", None):
        cfg.data.setdefault("io", {})["file_glob"] = args.pattern
    if getattr(args, "recursive", None) is not None:
        cfg.data.setdefault("io", {})["recursive"] = args.recursive
    return cfg


def _resolve_output_conflict(cfg, mode: str) -> None:
    """Handle an output folder that already has results: overwrite / copy / ask."""
    from .batch import output_has_results, timestamped_sibling
    if not output_has_results(cfg.output_dir):
        return
    if mode == "ask":
        ans = input(f"\n'{cfg.output_dir}' already has results.\n"
                    "  [o] overwrite   [c] save a new copy   [a] abort  ? ").strip().lower()
        mode = {"o": "overwrite", "c": "copy", "a": "abort"}.get(ans[:1], "overwrite")
    if mode == "copy":
        new = timestamped_sibling(cfg.output_dir)
        cfg.data["io"]["output_dir"] = str(new)
        print(f"Saving this run to a new copy: {new}")
    elif mode == "abort":
        raise SystemExit("Aborted — no changes made.")


def cmd_run(args) -> int:
    from .batch import run_batch, find_xdf_files
    from .pipeline import run_pipeline
    from .metadata import MetadataResolver
    from .batch import order_master_columns
    import pandas as pd

    cfg = _load(args)
    _resolve_output_conflict(cfg, getattr(args, "if_exists", "overwrite"))
    setup_logging(cfg.output_dir)

    if args.input:                       # single file
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        result = run_pipeline(args.input, cfg=cfg)
        # still emit a one-row master + run cohort stats (trivial cohort of 1)
        master = order_master_columns(pd.DataFrame([result.master_record]))
        master.to_csv(cfg.output_dir / "master_everything.csv", index=False)
        if not args.no_stats and cfg.get("stats", "enabled", True):
            from . import reporting
            reporting.build_cohort_outputs(cfg, master, [result], cfg.output_dir)
        info(f"\nDone. Outputs in: {cfg.output_dir}")
        return 0

    outputs = run_batch(cfg=cfg, run_stats=not args.no_stats)
    info(f"\nDone. Outputs in: {cfg.output_dir}")
    if "cohort_report" in outputs:
        info(f"Open the cohort report: {outputs['cohort_report']}")
    return 0


def cmd_streams(args) -> int:
    from .io_xdf import list_xdf_streams
    setup_logging(None)
    list_xdf_streams(args.file)
    return 0


def _silence_streamlit_prompt() -> None:
    """Stop Streamlit's first-run 'enter your email' prompt and usage telemetry, so
    the app opens straight to the interface (a senior scientist should never be asked
    to register or answer terminal questions)."""
    cred = Path.home() / ".streamlit" / "credentials.toml"
    if not cred.exists():
        cred.parent.mkdir(parents=True, exist_ok=True)
        cred.write_text('[general]\nemail = ""\n')


def cmd_gui(args) -> int:
    """Launch the native desktop GUI (fast, no web server)."""
    try:
        from . import gui
    except Exception as exc:
        print(f"Could not start the desktop GUI ({exc}).\n"
              "If Tkinter is unavailable, try the web GUI:  xon-pipeline webgui", file=sys.stderr)
        return 1
    return gui.main(config_path=args.config)


def cmd_webgui(args) -> int:
    """Launch the Streamlit web GUI (fallback / alternative to the desktop GUI)."""
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("The web GUI needs streamlit. Install it with:\n  pip install streamlit\n"
              "then re-run:  xon-pipeline webgui\n(Or just use the desktop GUI: xon-pipeline gui)",
              file=sys.stderr)
        return 1
    import subprocess
    _silence_streamlit_prompt()
    env = dict(os.environ)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_GLOBAL_SHOW_WARNING_ON_DIRECT_EXECUTION"] = "false"
    gui_path = Path(__file__).resolve().parent / "gui_web.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(gui_path),
           "--browser.gatherUsageStats", "false", "--server.headless", "false"]
    if args.config:
        cmd += ["--", "--config", args.config]
    return subprocess.call(cmd, env=env)


def cmd_export(args) -> int:
    """Make share-ready formats (figures.pdf, standalone HTML, bundle .zip) for a run."""
    from .reporting import export as EX
    out = Path(args.output) if args.output else load_config(args.config).output_dir
    if not out.exists():
        print(f"Output folder not found: {out}", file=sys.stderr)
        return 2
    paths = EX.export_all(out)
    if not paths:
        print(f"Nothing to export in {out} (run the pipeline first).", file=sys.stderr)
        return 1
    print("Exported:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    return 0


def cmd_config(args) -> int:
    import yaml
    cfg = _load(args)
    print(yaml.safe_dump(cfg.as_dict(), sort_keys=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xon-pipeline",
                                description="Xon .xdf EEG -> aperiodic exponent pipeline.")
    p.add_argument("--config", default=None, help="Path to config.yaml (default: repo config/config.yaml)")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Process a folder (or a single file).")
    r.add_argument("--input", default=None, help="A single .xdf file to process.")
    r.add_argument("--input-dir", default=None, help="Folder of .xdf files (overrides config).")
    r.add_argument("--output", default=None, help="Output folder (overrides config).")
    r.add_argument("--pattern", default=None, help="Glob for batch mode (e.g. '*' for extensionless).")
    r.add_argument("--recursive", dest="recursive", action="store_true", default=None,
                   help="Search sub-folders.")
    r.add_argument("--no-recursive", dest="recursive", action="store_false",
                   help="Do not search sub-folders.")
    r.add_argument("--no-stats", action="store_true", help="Skip cohort statistics/report.")
    r.add_argument("--if-exists", choices=["overwrite", "copy", "ask"], default="overwrite",
                   help="If the output folder already has results: overwrite, save a new "
                        "timestamped copy, or ask (default: overwrite).")
    r.add_argument("--set", action="append", metavar="section.key=value",
                   help="Override any config key (repeatable).")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("streams", help="List the streams in an .xdf file.")
    s.add_argument("file", help="Path to an .xdf file.")
    s.set_defaults(func=cmd_streams)

    g = sub.add_parser("gui", help="Launch the native desktop drag-and-drop GUI.")
    g.set_defaults(func=cmd_gui)

    w = sub.add_parser("webgui", help="Launch the Streamlit web GUI (alternative).")
    w.set_defaults(func=cmd_webgui)

    e = sub.add_parser("export", help="Make share-ready formats (PDF, standalone HTML, ZIP) for a run.")
    e.add_argument("--output", default=None, help="The run's output folder (default: config output_dir).")
    e.set_defaults(func=cmd_export)

    c = sub.add_parser("config", help="Print the resolved configuration and exit.")
    c.add_argument("--set", action="append", metavar="section.key=value")
    c.set_defaults(func=cmd_config)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
