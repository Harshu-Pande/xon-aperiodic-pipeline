"""Build one HTML 'contact sheet' of every recording's diagnostic figure, so you can
scan the whole cohort at a glance instead of opening dozens of PNGs one by one.

Each card shows the diagnostic image plus the headline numbers (exponent, r^2, %
rejected), is colour-flagged if the recording looks off, links to that recording's full
QC report, and its over-time / convergence plots. Click any image to open it full size.
"""
from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _num(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _exists(output_dir: Path, name: str) -> Optional[str]:
    return name if (output_dir / name).exists() else None


def build_gallery(output_dir: str | Path, master_df: pd.DataFrame,
                  filename: str = "gallery.html") -> str:
    """Write a gallery.html into output_dir and return its path."""
    output_dir = Path(output_dir)
    df = master_df.copy()
    if "status" in df.columns:
        df = df[df["status"].astype(str) != "error"]
    # sort by participant / session / condition when available
    for c in ["participant", "session", "condition"]:
        if c not in df.columns:
            df[c] = ""
    df = df.sort_values(["participant", "session", "condition"], kind="stable")

    # cohort summary numbers
    exps = pd.to_numeric(df.get("AVERAGE_exponent"), errors="coerce").dropna()
    r2s = pd.to_numeric(df.get("AVERAGE_r_squared"), errors="coerce").dropna()
    rej = pd.to_numeric(df.get("pct_epochs_rejected"), errors="coerce").dropna()
    summary = (
        f"{len(df)} recordings &middot; "
        f"mean exponent {exps.mean():.2f} (range {exps.min():.2f}–{exps.max():.2f}) &middot; "
        f"mean fit r&sup2; {r2s.mean():.3f} &middot; "
        f"median {rej.median():.0f}% epochs rejected"
        if len(exps) else f"{len(df)} recordings"
    )

    cards: List[str] = []
    for _, row in df.iterrows():
        sid = str(row.get("subject_id", ""))
        diag = _exists(output_dir, f"diagnostic_{sid}.png")
        conv = _exists(output_dir, f"durationcurve_{sid}.png")
        block = _exists(output_dir, f"block_exponents_{sid}.png")
        qc = _exists(output_dir, f"qc_report_{sid}.html")
        exp = _num(row.get("AVERAGE_exponent"))
        r2 = _num(row.get("AVERAGE_r_squared"))
        pr = _num(row.get("pct_epochs_rejected"))
        worst = row.get("worst_reject_channel", "")

        # flag colour: red if noisy or poor fit, amber if middling, else green
        flag = "#2a9d8f"
        note = "looks clean"
        if (pr is not None and pr >= 50) or (r2 is not None and r2 < 0.9):
            flag, note = "#e63946", "check this one"
        elif (pr is not None and pr >= 25) or (r2 is not None and r2 < 0.95):
            flag, note = "#e9a23b", "some rejection"

        img = (f"<a href='{html.escape(diag)}' target='_blank'>"
               f"<img loading='lazy' src='{html.escape(diag)}'></a>") if diag else \
              "<div class='noimg'>no diagnostic image</div>"
        badges = " ".join(filter(None, [
            f"<b>exp {exp:.2f}</b>" if exp is not None else "",
            f"r&sup2; {r2:.3f}" if r2 is not None else "",
            f"{pr:.0f}% rej" if pr is not None else "",
            f"worst: {html.escape(str(worst))}" if worst else "",
        ]))
        links = " &middot; ".join(filter(None, [
            f"<a href='{html.escape(qc)}' target='_blank'>QC report</a>" if qc else "",
            f"<a href='{html.escape(block)}' target='_blank'>over time</a>" if block else "",
            f"<a href='{html.escape(conv)}' target='_blank'>vs length</a>" if conv else "",
        ]))
        label = " · ".join(filter(None, [str(row.get("participant", "")),
                                         (f"S{row.get('session')}" if row.get("session") else ""),
                                         str(row.get("condition", ""))])) or sid
        cards.append(
            f"<div class='card' style='border-top:5px solid {flag}' "
            f"data-cond='{html.escape(str(row.get('condition','')))}' data-flag='{note}'>"
            f"<div class='hd'><span class='ttl'>{html.escape(label)}</span>"
            f"<span class='tag' style='background:{flag}'>{note}</span></div>"
            f"{img}<div class='badges'>{badges}</div><div class='links'>{links}</div></div>")

    doc = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Diagnostics gallery</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:1.5rem;color:#22333b;background:#fafbfc}}
h1{{font-size:1.5rem;margin:0 0 4px}}
.sub{{color:#5a6b7b;margin-bottom:14px}}
.controls{{margin:10px 0 18px}}
.controls button{{border:1px solid #cdd6df;background:#fff;border-radius:20px;padding:6px 14px;margin-right:6px;cursor:pointer;font-size:.85rem}}
.controls button.active{{background:#22333b;color:#fff;border-color:#22333b}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px}}
.card{{background:#fff;border:1px solid #e6e9ee;border-radius:10px;padding:10px 12px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.card img{{width:100%;border-radius:6px;cursor:zoom-in}}
.noimg{{padding:40px;text-align:center;color:#aab;background:#f3f5f7;border-radius:6px}}
.hd{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.ttl{{font-weight:700}}
.tag{{color:#fff;font-size:.7rem;padding:2px 8px;border-radius:10px}}
.badges{{margin-top:8px;font-size:.85rem;color:#33475b}} .badges b{{color:#12263a}}
.links{{margin-top:4px;font-size:.8rem}} .links a{{color:#2a6f97;text-decoration:none}}
</style></head><body>
<h1>Diagnostics gallery</h1>
<div class='sub'>{summary}</div>
<div class='controls'>
  <button class='active' onclick="filt(this,'all')">All</button>
  <button onclick="filt(this,'rest')">Rest</button>
  <button onclick="filt(this,'movie')">Movie</button>
  <button onclick="filt(this,'check this one')">⚠ Needs a look</button>
</div>
<div class='grid' id='grid'>{''.join(cards)}</div>
<script>
function filt(btn, key){{
  document.querySelectorAll('.controls button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(c=>{{
    let show = key==='all' || c.dataset.cond===key || c.dataset.flag===key;
    c.style.display = show ? '' : 'none';
  }});
}}
</script></body></html>"""
    out = output_dir / filename
    with open(out, "w") as fh:
        fh.write(doc)
    return str(out)
