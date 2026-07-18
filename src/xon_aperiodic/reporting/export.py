"""Export results for sharing / presentations, in several robust formats:

* a **figures PDF** (all publication figures, one per page) built with matplotlib — no
  fragile HTML->PDF converter needed;
* a **self-contained HTML** report/gallery (images embedded as base64) that is a single
  portable file you can email or open on any computer;
* a **shareable ZIP** bundling the report, gallery, figures, statistics and the above.

For a PDF of the full formatted report, the most reliable path on any machine is the
browser's own "Save as PDF" (the reports carry print-friendly CSS); the GUI offers that.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages


# --------------------------------------------------------------------------
# figures -> a single multi-page PDF (great for slide decks)
# --------------------------------------------------------------------------
_FIG_ORDER = [
    "fig_reliability_by_duration", "fig_duration_overlay", "fig_test_retest",
    "fig_bland_altman", "fig_regional", "fig_condition_paired",
    "fig_exponent_by_condition", "fig_quality",
]


def export_figures_pdf(output_dir: str | Path, pdf_name: str = "figures.pdf") -> Optional[str]:
    output_dir = Path(output_dir)
    fig_dir = output_dir / "figures"
    if not fig_dir.exists():
        return None
    pngs = sorted(fig_dir.glob("*.png"))
    if not pngs:
        return None
    # order the known figures first, then any extras
    order = {name: i for i, name in enumerate(_FIG_ORDER)}
    pngs.sort(key=lambda p: order.get(p.stem, 999))
    out = output_dir / pdf_name
    with PdfPages(out) as pdf:
        for png in pngs:
            try:
                img = mpimg.imread(png)
            except Exception:
                continue
            h, w = img.shape[0], img.shape[1]
            fig = plt.figure(figsize=(11, 8.5))
            ax = fig.add_axes([0.03, 0.03, 0.94, 0.90])
            ax.imshow(img); ax.axis("off")
            fig.suptitle(png.stem.replace("fig_", "").replace("_", " "), fontsize=13)
            pdf.savefig(fig, dpi=200); plt.close(fig)
        d = pdf.infodict(); d["Title"] = "Xon aperiodic — figures"; d["CreationDate"] = datetime.now()
    return str(out)


# --------------------------------------------------------------------------
# HTML with images inlined -> one portable file
# --------------------------------------------------------------------------
def _inline_images(html: str, base_dir: Path) -> str:
    def repl(m):
        quote, src = m.group(1), m.group(2)
        if src.startswith(("data:", "http://", "https://")):
            return m.group(0)
        img_path = (base_dir / src).resolve()
        if not img_path.exists():
            return m.group(0)
        mime = mimetypes.guess_type(str(img_path))[0] or "image/png"
        try:
            data = base64.b64encode(img_path.read_bytes()).decode("ascii")
        except Exception:
            return m.group(0)
        return f"src={quote}data:{mime};base64,{data}{quote}"
    return re.sub(r"src=(['\"])([^'\"]+)\1", repl, html)


def make_standalone_html(html_path: str | Path, out_name: Optional[str] = None) -> Optional[str]:
    html_path = Path(html_path)
    if not html_path.exists():
        return None
    html = html_path.read_text()
    standalone = _inline_images(html, html_path.parent)
    out = html_path.with_name(out_name or (html_path.stem + "_standalone.html"))
    out.write_text(standalone)
    return str(out)


# --------------------------------------------------------------------------
# shareable ZIP
# --------------------------------------------------------------------------
def make_bundle(output_dir: str | Path, zip_name: Optional[str] = None) -> Optional[str]:
    output_dir = Path(output_dir)
    stamp = datetime.now().strftime("%Y%m%d")
    zip_path = output_dir / (zip_name or f"xon_results_bundle_{stamp}.zip")
    items: List[Path] = []
    for name in ["cohort_report.html", "gallery.html", "master_everything.csv",
                 "cohort_report_standalone.html", "gallery_standalone.html", "figures.pdf"]:
        p = output_dir / name
        if p.exists():
            items.append(p)
    for sub in ["figures", "statistics"]:
        d = output_dir / sub
        if d.exists():
            items.extend(sorted(d.rglob("*")))
    if not items:
        return None
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in items:
            if p.is_file():
                zf.write(p, p.relative_to(output_dir))
    return str(zip_path)


def export_all(output_dir: str | Path) -> Dict[str, str]:
    """Produce every share format for a completed run. Returns paths that were created."""
    output_dir = Path(output_dir)
    paths: Dict[str, str] = {}
    pdf = export_figures_pdf(output_dir)
    if pdf:
        paths["figures_pdf"] = pdf
    for html_name, key in [("cohort_report.html", "report_standalone"),
                           ("gallery.html", "gallery_standalone")]:
        s = make_standalone_html(output_dir / html_name)
        if s:
            paths[key] = s
    bundle = make_bundle(output_dir)
    if bundle:
        paths["bundle_zip"] = bundle
    return paths
