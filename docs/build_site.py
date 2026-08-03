"""Build the single-file HTML documentation.

Produces ONE self-contained file — docs/Xon_Pipeline_Documentation.html — containing all
four documents. It behaves like a multi-page site (sidebar, tabbed pages, live search,
per-page contents) but is a single file with no external assets, so it can be emailed and
opened anywhere, offline.

    python3 docs/build_site.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent

PAGES = [
    ("home",     "Overview",                 None),
    ("methods",  "Methods &amp; Literature",     "1_METHODS_AND_LITERATURE.md"),
    ("setup",    "Setup &amp; Running",          "2_SETUP_AND_RUNNING.md"),
    ("code",     "Code Walkthrough",         "3_CODE_WALKTHROUGH.md"),
    ("outputs",  "Outputs &amp; Analysis",       "4_OUTPUTS_AND_ANALYSIS.md"),
]

# ── palette ────────────────────────────────────────────────────────────────────
# Calm, professional, high-contrast. Deep navy structure + teal accent; no loud red.
NAVY, NAVY_D, TEAL, TEAL_D = "#243b53", "#102a43", "#2a9d8f", "#1d7a6f"
AMBER, PLUM, ROSE = "#c98a2b", "#7b5ea7", "#b5566d"

CSS = f"""
:root{{
 --navy:{NAVY};--navy-d:{NAVY_D};--teal:{TEAL};--teal-d:{TEAL_D};
 --amber:{AMBER};--plum:{PLUM};--rose:{ROSE};
 --ink:#1c2733;--body:#33445c;--mut:#6b7c93;--line:#e1e7ee;--line-s:#eef2f6;
 --bg:#f5f7fa;--card:#fff;--code-bg:#eef2f6;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;font:16px/1.68 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 color:var(--body);background:var(--bg);-webkit-font-smoothing:antialiased}}
.wrap{{display:flex;align-items:flex-start;min-height:100vh}}

/* ── sidebar ── */
nav{{width:296px;flex:0 0 296px;background:var(--card);border-right:1px solid var(--line);
 position:sticky;top:0;height:100vh;overflow-y:auto;padding-bottom:40px}}
nav .brand{{background:linear-gradient(150deg,var(--navy),var(--navy-d));color:#fff;padding:22px 22px 20px}}
nav .brand b{{display:block;font-size:1.06rem;letter-spacing:.2px}}
nav .brand span{{font-size:.79rem;opacity:.82;display:block;margin-top:3px}}
.searchbox{{padding:14px 18px 8px}}
.searchbox input{{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;
 font-size:.88rem;color:var(--ink);background:#fbfcfd;outline:none}}
.searchbox input:focus{{border-color:var(--teal);box-shadow:0 0 0 3px rgba(42,157,143,.13)}}
.navsec{{padding:14px 22px 5px;font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:var(--mut)}}
.navlink{{display:flex;align-items:center;gap:10px;padding:10px 20px;color:var(--body);
 text-decoration:none;font-size:.93rem;border-left:3px solid transparent;cursor:pointer}}
.navlink:hover{{background:var(--line-s)}}
.navlink.active{{background:#eef7f6;border-left-color:var(--teal);color:var(--teal-d);font-weight:650}}
.navlink .n{{width:22px;height:22px;flex:0 0 22px;border-radius:6px;background:var(--line-s);
 color:var(--mut);font-size:.72rem;font-weight:700;display:grid;place-items:center}}
.navlink.active .n{{background:var(--teal);color:#fff}}
.subnav{{display:none;padding:2px 0 8px}}
.subnav.show{{display:block}}
.subnav a{{display:block;padding:5px 20px 5px 52px;font-size:.845rem;color:var(--mut);text-decoration:none;
 border-left:2px solid var(--line);margin-left:20px}}
.subnav a:hover{{color:var(--teal-d);border-left-color:var(--teal)}}

/* ── content ── */
main{{flex:1;min-width:0;padding:40px 54px 100px;max-width:1060px}}
.page{{display:none;animation:fade .18s ease}}
.page.active{{display:block}}
@keyframes fade{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
h1{{font-size:2rem;margin:.05em 0 .5em;color:var(--ink);letter-spacing:-.35px;line-height:1.25}}
h2{{font-size:1.36rem;margin:2em 0 .55em;color:var(--ink);padding-bottom:9px;
 border-bottom:1px solid var(--line);scroll-margin-top:16px}}
h3{{font-size:1.09rem;margin:1.6em 0 .4em;color:var(--teal-d);scroll-margin-top:16px}}
h4{{font-size:.98rem;margin:1.25em 0 .3em;color:var(--ink)}}
p{{margin:.65em 0}}
code{{background:var(--code-bg);padding:2px 6px;border-radius:5px;font-size:.865em;color:#1d3a4d;
 font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
pre{{background:var(--navy-d);color:#e6edf5;padding:16px 18px;border-radius:10px;overflow-x:auto;
 font-size:.855rem;line-height:1.55;margin:1em 0}}
pre code{{background:none;color:inherit;padding:0;font-size:inherit}}
table{{border-collapse:separate;border-spacing:0;width:100%;margin:1.1em 0;font-size:.895rem;
 background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th{{background:#f0f4f8;text-align:left;font-weight:650;color:var(--ink)}}
th,td{{padding:9px 12px;vertical-align:top;border-bottom:1px solid var(--line-s)}}
tr:last-child td{{border-bottom:0}}
tbody tr:hover td{{background:#fbfcfe}}
blockquote{{margin:1.15em 0;padding:13px 18px;background:#fff9ec;border-left:4px solid var(--amber);
 border-radius:0 8px 8px 0;color:#5a4a2e}}
blockquote p{{margin:.25em 0}}
blockquote code{{background:#f3e7cd}}
ul,ol{{margin:.55em 0;padding-left:1.45em}}
li{{margin:.26em 0}}
hr{{border:0;border-top:1px solid var(--line);margin:2em 0}}
a{{color:var(--teal-d)}}
strong{{color:var(--ink)}}

/* ── components ── */
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(238px,1fr));gap:15px;margin:1.4em 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:19px 20px;
 text-decoration:none;color:inherit;display:block;transition:.16s;cursor:pointer}}
.card:hover{{border-color:var(--teal);box-shadow:0 6px 18px rgba(36,59,83,.09);transform:translateY(-2px)}}
.card .num{{width:26px;height:26px;border-radius:7px;background:var(--teal);color:#fff;font-size:.78rem;
 font-weight:700;display:grid;place-items:center;margin-bottom:10px}}
.card b{{display:block;color:var(--ink);margin-bottom:5px;font-size:1.01rem}}
.card span{{font-size:.865rem;color:var(--mut);line-height:1.5}}
.hero{{background:linear-gradient(140deg,var(--navy),var(--navy-d));color:#fff;padding:34px 36px;
 border-radius:14px;margin-bottom:8px}}
.hero h1{{color:#fff;margin:0 0 10px;font-size:1.95rem}}
.hero p{{margin:0;opacity:.9;max-width:62ch}}
.fig{{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:20px;
 margin:1.5em 0;text-align:center}}
.fig svg{{max-width:100%;height:auto}}
.fig figcaption{{font-size:.83rem;color:var(--mut);margin-top:11px;font-style:italic}}
.pill{{display:inline-block;font-size:.71rem;font-weight:700;padding:2px 9px;border-radius:11px;
 vertical-align:middle;letter-spacing:.3px}}
.on{{background:#e2f4ef;color:#1d7a6f}} .off{{background:#fdeaee;color:#a8405a}}
.always{{background:#eef2f6;color:#5b6b80}}
.toplink{{position:fixed;right:24px;bottom:24px;background:var(--navy);color:#fff;border:0;
 width:42px;height:42px;border-radius:50%;font-size:1.1rem;cursor:pointer;display:none;
 box-shadow:0 4px 14px rgba(16,42,67,.28)}}
.toplink.show{{display:block}}
mark{{background:#ffeaa7;padding:1px 2px;border-radius:3px}}
.nores{{color:var(--mut);font-size:.85rem;padding:8px 22px;font-style:italic}}

@media(max-width:900px){{.wrap{{display:block}}nav{{width:auto;height:auto;position:static;flex:none}}
 main{{padding:24px 18px 70px}}}}
@media print{{
 nav,.toplink{{display:none}} main{{padding:0;max-width:none}}
 .page{{display:block!important}} .page+.page{{page-break-before:always}}
 .card:hover{{transform:none;box-shadow:none}} a{{color:inherit;text-decoration:none}}
}}
"""


# ── markdown subset ────────────────────────────────────────────────────────────
def md_inline(s: str) -> str:
    s = html.escape(s, quote=False)
    spans: list[str] = []

    def _stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    s = re.sub(r"`([^`]+)`", _stash, s)                       # protect inline code first
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s)
    s = re.sub(r"\*\*(.+?)\*\*(?!\*)", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)

    def _link(m):
        text, href = m.group(1), m.group(2)
        for pid, _t, src in PAGES:
            if src and (href.endswith(src) or href == src):
                return f'<a href="#" data-goto="{pid}">{text}</a>'
        return f'<a href="{href}">{text}</a>'

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, s)
    s = s.replace("🟢", '<span class="pill on">ON</span>')
    s = s.replace("🔴", '<span class="pill off">OFF</span>')
    s = s.replace("⚙️", '<span class="pill always">ALWAYS</span>')
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)


def slug(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    return re.sub(r"[\s_]+", "-", t)


def md_to_html(md: str):
    out, toc = [], []
    lines = md.split("\n")
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl, txt = len(m.group(1)), md_inline(m.group(2))
            a = slug(m.group(2))
            if lvl <= 3:
                toc.append((lvl, re.sub(r"<[^>]+>", "", txt), a))
            out.append(f'<h{lvl} id="{a}">{txt}</h{lvl}>')
            i += 1
            continue
        if ln.strip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            t = ["<table><thead><tr>"] + [f"<th>{md_inline(h)}</th>" for h in head] + ["</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        if re.match(r"^\s*>", ln):
            buf = []
            while i < n and re.match(r"^\s*>", lines[i]):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            inner, _ = md_to_html("\n".join(buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue
        if re.match(r"^\s*([-*+]|\d+\.)\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s+", ln))
            items = []
            while i < n and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                item = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i]); i += 1
                while i < n and lines[i].startswith("  ") and not re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]) \
                        and lines[i].strip():
                    item += " " + lines[i].strip(); i += 1
                items.append(f"<li>{md_inline(item)}</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if re.match(r"^\s*(---+|\*\*\*+)\s*$", ln):
            out.append("<hr>"); i += 1; continue
        if not ln.strip():
            i += 1; continue
        buf = [ln]; i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(\s*[-*+]\s|\s*\d+\.\s|#{1,4}\s|```|\s*\||\s*>)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append("<p>" + md_inline(" ".join(buf)) + "</p>")
    return "\n".join(out), toc


# ── diagrams (recoloured to the new palette) ───────────────────────────────────
def svg_flow() -> str:
    steps = [("&#46;xdf file", "io_xdf&#46;py", "#5b6b80"), ("Metadata", "metadata&#46;py", "#5b6b80"),
             ("Preprocess", "filter &#183; bad channels", NAVY), ("Channel screen", "ON by default", TEAL),
             ("Epoch + reject", "4 mechanisms", AMBER), ("Welch &#8594; FOOOF", "exponent", PLUM),
             ("Cohort report", "reporting/", NAVY_D)]
    w, bw, bh, gap = 980, 124, 62, 14
    p = [f'<svg viewBox="0 0 {w} 150" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">',
         '<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
         '<path d="M0,0 L0,6 L8,3 z" fill="#9fb0c4"/></marker></defs>',
         f'<text x="{w/2}" y="20" text-anchor="middle" fill="#1c2733" font-size="12.5" '
         f'font-weight="700">One recording, end to end</text>']
    x, y = 6, 40
    for i, (t, s, c) in enumerate(steps):
        p.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="9" fill="{c}"/>')
        p.append(f'<text x="{x+bw/2}" y="{y+25}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{t}</text>')
        p.append(f'<text x="{x+bw/2}" y="{y+44}" text-anchor="middle" fill="#fff" font-size="10.5" opacity=".9">{s}</text>')
        if i < len(steps) - 1:
            p.append(f'<path d="M{x+bw+2} {y+bh/2} L{x+bw+gap-3} {y+bh/2}" stroke="#9fb0c4" stroke-width="2" marker-end="url(#ah)"/>')
        x += bw + gap
    p.append(f'<text x="{w/2}" y="{y+bh+24}" text-anchor="middle" fill="#6b7c93" font-size="11">'
             'PASS 2 re-runs the bracketed stages if a channel&#8217;s final exponent &lt; 0.5 '
             '&#8212; so the exponent we reject on is the exponent we report</text></svg>')
    return "".join(p)


def svg_reject() -> str:
    mech = [("Amplitude / flat", "&gt;100 &#181;V p-p", NAVY), ("Gradient", "&gt;10 &#181;V/ms", AMBER),
            ("Variance z", "&gt; 3", TEAL), ("Muscle z", "&gt; 3 on &gt;30 Hz", PLUM)]
    w = 940
    p = [f'<svg viewBox="0 0 {w} 240" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">',
         '<defs><marker id="ah2" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
         '<path d="M0,0 L0,6 L8,3 z" fill="#9fb0c4"/></marker></defs>',
         f'<text x="{w/2}" y="18" text-anchor="middle" font-size="12.5" font-weight="700" fill="#1c2733">'
         'Four rejection mechanisms &#8212; each hit attributed to the channel that caused it</text>']
    x = 20
    for name, thr, col in mech:
        p.append(f'<rect x="{x}" y="36" width="200" height="58" rx="9" fill="{col}" opacity=".12" stroke="{col}" stroke-width="1.6"/>')
        p.append(f'<text x="{x+100}" y="59" text-anchor="middle" font-size="12.5" font-weight="700" fill="{col}">{name}</text>')
        p.append(f'<text x="{x+100}" y="78" text-anchor="middle" font-size="11" fill="#6b7c93">{thr}</text>')
        p.append(f'<path d="M{x+100} 96 L{x+100} 118" stroke="#9fb0c4" stroke-width="1.8" marker-end="url(#ah2)"/>')
        x += 230
    p.append(f'<rect x="20" y="120" width="900" height="52" rx="9" fill="{NAVY_D}"/>')
    p.append('<text x="470" y="139" text-anchor="middle" font-size="12" fill="#fff">Per-channel counters recorded in the master CSV</text>')
    p.append('<text x="470" y="158" text-anchor="middle" font-size="11.5" fill="#8fd8cd" '
             'font-family="ui-monospace,Menlo,Consolas,monospace">'
             '{CH}_amp_flat_hits &#183; _gradient_hits &#183; _variance_hits &#183; _muscle_hits</text>')
    p.append('<path d="M470 174 L470 190" stroke="#9fb0c4" stroke-width="1.8" marker-end="url(#ah2)"/>')
    p.append(f'<rect x="230" y="192" width="480" height="38" rx="9" fill="{TEAL_D}"/>')
    p.append('<text x="470" y="216" text-anchor="middle" font-size="12.5" fill="#fff" font-weight="700">'
             'worst_reject_channel &#183; worst_reject_channel_share</text></svg>')
    return "".join(p)


def svg_montage() -> str:
    coords = {"Fp1": (-.31, .95), "Fp2": (.31, .95), "F7": (-.81, .59), "F3": (-.41, .61), "Fz": (0, .63),
              "F4": (.41, .61), "F8": (.81, .59), "T7": (-1, 0), "C3": (-.5, 0), "Cz": (0, 0), "C4": (.5, 0),
              "T8": (1, 0), "P7": (-.81, -.59), "P3": (-.41, -.61), "Pz": (0, -.63), "P4": (.41, -.61),
              "P8": (.81, -.59), "O1": (-.31, -.95), "O2": (.31, -.95)}
    reg = {"F3": PLUM, "F4": PLUM, "C3": TEAL_D, "C4": TEAL_D, "Cz": TEAL_D, "P3": ROSE, "P4": ROSE}
    R, cx, cy = 132, 175, 175
    p = ['<svg viewBox="0 0 350 400" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">',
         f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{NAVY}" stroke-width="3"/>',
         f'<path d="M{cx-15} {cy-R+2} L{cx} {cy-R-18} L{cx+15} {cy-R+2}" fill="none" stroke="{NAVY}" '
         'stroke-width="3" stroke-linejoin="round"/>']
    for ch, (ux, uy) in coords.items():
        X, Y = cx + ux * R, cy - uy * R
        if ch in reg:
            p.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="19" fill="{reg[ch]}" stroke="#fff" stroke-width="2.5"/>')
            p.append(f'<text x="{X:.1f}" y="{Y+4.5:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">{ch}</text>')
        else:
            p.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="14" fill="#eef2f6" stroke="#cdd8e3" stroke-width="1.3"/>')
            p.append(f'<text x="{X:.1f}" y="{Y+3.5:.1f}" text-anchor="middle" font-size="9" fill="#9fb0c4">{ch}</text>')
    ly = 330
    for lbl, col in [("Frontal (F3, F4)", PLUM), ("Central (C3, C4, Cz)", TEAL_D), ("Parietal (P3, P4)", ROSE)]:
        p.append(f'<rect x="60" y="{ly-10}" width="15" height="15" rx="3" fill="{col}"/>')
        p.append(f'<text x="84" y="{ly+2}" font-size="12" fill="#1c2733">{lbl}</text>')
        ly += 22
    p.append("</svg>")
    return "".join(p)


def svg_minutes() -> str:
    w = 900
    p = [f'<svg viewBox="0 0 {w} 268" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">',
         f'<text x="{w/2}" y="18" text-anchor="middle" font-size="12.5" font-weight="700" fill="#1c2733">'
         'Two different &#8220;how many minutes are enough?&#8221; questions</text>']
    x0, x1, ax = 70, 830, 150
    p.append(f'<line x1="{x0}" y1="{ax}" x2="{x1}" y2="{ax}" stroke="#9fb0c4" stroke-width="2"/>')
    for mins in range(0, 31, 5):
        X = x0 + (x1 - x0) * mins / 30
        p.append(f'<line x1="{X}" y1="{ax-4}" x2="{X}" y2="{ax+4}" stroke="#9fb0c4" stroke-width="1.5"/>')
        p.append(f'<text x="{X}" y="{ax+20}" text-anchor="middle" font-size="10.5" fill="#6b7c93">{mins}</text>')
    p.append(f'<text x="{(x0+x1)/2}" y="{ax+40}" text-anchor="middle" font-size="11.5" fill="#6b7c93">clean minutes</text>')
    for mins, ytop, col, bold, sub in [
            (1, 60, TEAL_D, "~1 min", "Reliability (rank-ordering people) is reached"),
            (14.25, 98, AMBER, "~14 min &#8212; typically precise", "odd/even halves agree (minutes_to_stabilize)"),
            (17, 128, PLUM, "~17 min &#8212; typically full value", "(minutes_to_converge)")]:
        X = x0 + (x1 - x0) * mins / 30
        p.append(f'<line x1="{X}" y1="{ax}" x2="{X}" y2="{ytop}" stroke="{col}" stroke-width="2.5"/>')
        p.append(f'<circle cx="{X}" cy="{ytop}" r="6" fill="{col}"/>')
        p.append(f'<text x="{X+12}" y="{ytop-4}" font-size="12" font-weight="700" fill="{col}">{bold}</text>')
        p.append(f'<text x="{X+12}" y="{ytop+12}" font-size="11" fill="#6b7c93">{sub}</text>')
    p.append(f'<rect x="{x0}" y="204" width="{x1-x0}" height="48" rx="9" fill="#fff9ec" stroke="{AMBER}"/>')
    p.append(f'<text x="{(x0+x1)/2}" y="224" text-anchor="middle" font-size="12" font-weight="700" fill="#1c2733">'
             'Short data ranks people reliably; the absolute value keeps drifting for ~10&#8211;17 min.</text>')
    p.append(f'<text x="{(x0+x1)/2}" y="242" text-anchor="middle" font-size="11.5" fill="#6b7c93">'
             'A short recording can be precise but biased LOW. (Illustrative &#8212; your run will differ.)</text></svg>')
    return "".join(p)


DIAGRAMS = {
    "methods": [("## 1.7", svg_minutes(), "The two distinct duration questions, on one axis.")],
    "code": [("## The flow, end to end", svg_flow(), "Module-by-module flow for a single recording."),
             ("### `reject_artifacts()`", svg_reject(),
              "Rejection mechanisms and the per-channel attribution they feed.")],
    "outputs": [("### Scalp region", svg_montage(),
                 "The 7 Xon electrodes on the 10-20 layout, coloured by region.")],
}

# Everything here runs inside an IIFE. That is not style: at top level, `const top`
# collides with the built-in `window.top` and throws
#     SyntaxError: Identifier 'top' has already been declared
# which kills the WHOLE script before a line of it runs - so the sidebar, the search and
# every in-page link silently stop working with no visible error. A function scope makes
# such a name legal (it just shadows), and 'use strict' surfaces the next typo instead of
# creating a global. The names below are also chosen to avoid the other window globals
# that bite here: name, status, length, closed, parent, self, history, origin.
JS = """
(function(){
'use strict';
const pages=[...document.querySelectorAll('.page')];
const links=[...document.querySelectorAll('.navlink')];
function show(id,push){
  pages.forEach(p=>p.classList.toggle('active',p.id==='page-'+id));
  links.forEach(l=>l.classList.toggle('active',l.dataset.page===id));
  document.querySelectorAll('.subnav').forEach(s=>s.classList.toggle('show',s.dataset.for===id));
  window.scrollTo({top:0,behavior:'instant'});
  // This file is meant to be opened straight off disk, and some browsers refuse
  // history.replaceState on a file:// URL with a SecurityError. Losing the address-bar
  // anchor is cosmetic; letting the exception escape would abort the click handler.
  if(push!==false){try{history.replaceState(null,'','#'+id);}catch(e){}}
}
links.forEach(l=>l.addEventListener('click',e=>{e.preventDefault();show(l.dataset.page)}));
document.addEventListener('click',e=>{
  const g=e.target.closest('[data-goto]'); if(g){e.preventDefault();show(g.dataset.goto);}
  const s=e.target.closest('.subnav a');
  if(s){e.preventDefault();const el=document.querySelector(s.getAttribute('href'));
        if(el)el.scrollIntoView({behavior:'smooth',block:'start'});}
});
show((location.hash||'#home').slice(1),false);

/* search across every heading in every page */
const box=document.getElementById('q'), res=document.getElementById('qres');
const idx=[];
pages.forEach(p=>{const pid=p.id.replace('page-','');
  p.querySelectorAll('h1,h2,h3,h4').forEach(h=>idx.push({pid,id:h.id,txt:h.textContent.trim()}));});
box.addEventListener('input',()=>{
  const v=box.value.trim().toLowerCase(); res.innerHTML='';
  if(v.length<2){res.style.display='none';return;}
  const hits=idx.filter(o=>o.txt.toLowerCase().includes(v)).slice(0,12);
  res.style.display='block';
  if(!hits.length){res.innerHTML='<div class="nores">No match</div>';return;}
  hits.forEach(o=>{const a=document.createElement('a');
    a.className='navlink';a.style.paddingLeft='22px';a.style.fontSize='.85rem';
    a.innerHTML=o.txt.replace(new RegExp('('+v.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','ig'),'<mark>$1</mark>');
    a.href='#';a.addEventListener('click',ev=>{ev.preventDefault();show(o.pid);
      setTimeout(()=>{const el=document.getElementById(o.id);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});},60);
      box.value='';res.style.display='none';});
    res.appendChild(a);});
});
const topBtn=document.querySelector('.toplink');
if(topBtn){
  addEventListener('scroll',()=>topBtn.classList.toggle('show',scrollY>500));
  topBtn.addEventListener('click',()=>scrollTo({top:0,behavior:'smooth'}));
}
})();
"""


def build():
    sections, navitems = [], []
    for pid, title, src in PAGES:
        if src is None:
            continue
        md = (DOCS / src).read_text(encoding="utf-8")
        body, toc = md_to_html(md)
        body = re.sub(r'(<h[1-4]) id="([^"]*)"', rf'\1 id="{pid}--\2"', body)
        for anchor, svg, cap in DIAGRAMS.get(pid, []):
            m = re.match(r"^(#+)\s+(.*)$", anchor)
            lvl, prefix = len(m.group(1)), m.group(2).strip()
            fig = f'<figure class="fig">{svg}<figcaption>{cap}</figcaption></figure>'
            placed = False
            for hm in re.finditer(rf'<h{lvl} id="[^"]*">(.*?)</h{lvl}>', body, re.S):
                plain = re.sub(r"<[^>]+>", "", hm.group(1)).replace("&amp;", "&").strip()
                if plain.startswith(prefix.replace("`", "")):
                    body = body[:hm.end()] + fig + body[hm.end():]; placed = True; break
            if not placed:
                raise SystemExit(f"DIAGRAM ANCHOR NOT FOUND on {pid}: {anchor!r}")
        sections.append(f'<div class="page" id="page-{pid}">{body}</div>')
        subs = "".join(f'<a href="#{pid}--{a}">{html.escape(t)}</a>' for lvl, t, a in toc if lvl == 2)
        navitems.append((pid, title, subs))

    nav = ['<nav><div class="brand"><b>Xon Aperiodic Pipeline</b>'
           '<span>Complete documentation &middot; single file</span></div>',
           '<div class="searchbox"><input id="q" type="search" placeholder="Search the docs…" '
           'autocomplete="off"></div><div id="qres" style="display:none"></div>',
           '<div class="navsec">Contents</div>',
           '<a class="navlink" data-page="home" href="#home"><span class="n">&#9679;</span>Overview</a>']
    for i, (pid, title, subs) in enumerate(navitems, 1):
        nav.append(f'<a class="navlink" data-page="{pid}" href="#{pid}"><span class="n">{i}</span>{title}</a>')
        if subs:
            nav.append(f'<div class="subnav" data-for="{pid}">{subs}</div>')
    nav.append("</nav>")

    cards = "".join(
        f'<a class="card" data-goto="{i}"><div class="num">{n}</div><b>{t}</b><span>{d}</span></a>'
        for n, i, t, d in [
            (1, "methods", "Methods &amp; Literature", "Why every setting is what it is — with the papers behind it."),
            (2, "setup", "Setup &amp; Running", "Install, run and troubleshoot. Non-coder and coder tracks."),
            (3, "code", "Code Walkthrough", "Every module and function; what it does and whether it's ON by default."),
            (4, "outputs", "Outputs &amp; Analysis", "Every output file, every analysis, and the full master-CSV dictionary."),
        ])
    home = f"""<div class="page active" id="page-home">
<div class="hero"><h1>Xon Aperiodic Pipeline</h1>
<p>Turning 7-channel Xon <code style="background:rgba(255,255,255,.16);color:#fff">.xdf</code>
recordings into the EEG aperiodic exponent — reliably, reproducibly, and entirely offline.
This single file is the complete documentation.</p></div>
<h2 id="home--start">Start here</h2>
<div class="cards">{cards}</div>
<figure class="fig">{svg_flow()}<figcaption>How one recording moves through the pipeline.</figcaption></figure>
<h2 id="home--quick">The 60-second version</h2>
<ul>
<li><b>Run it</b> — double-click <code>Start Here (Mac).command</code> or
<code>Start Here (Windows).bat</code>, choose an input and output folder, press Run.</li>
<li><b>Read it</b> — open <code>cohort_report.html</code> in the output folder.</li>
<li><b>Analyse it</b> — <code>master_everything.csv</code>: one wide row per recording,
including <i>why</i> each channel caused rejections.</li>
<li><b>Change it</b> — everything lives in <code>config/config.yaml</code>, or tick it in the GUI.</li>
</ul>
<blockquote><p><b>What this pipeline can and cannot tell you.</b> It measures the aperiodic
exponent <b>reliably and reproducibly</b>. Without a simultaneous research-grade EEG
reference it cannot establish <b>absolute accuracy</b> — that distinction is carried
throughout these documents.</p></blockquote>
<h2 id="home--where">Where things live</h2>
<table><thead><tr><th>Path</th><th>What</th></tr></thead><tbody>
<tr><td><code>config/config.yaml</code></td><td>every setting, commented</td></tr>
<tr><td><code>src/xon_aperiodic/</code></td><td>the pipeline modules</td></tr>
<tr><td><code>scripts/</code></td><td>launchers and the auto-updater</td></tr>
<tr><td><code>docs/</code></td><td>these four documents (<code>archive/</code> = superseded)</td></tr>
<tr><td><code>tests/</code></td><td>synthetic tests — no patient data</td></tr>
</tbody></table></div>"""

    doc = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Xon Aperiodic Pipeline — Documentation</title><style>{CSS}</style></head>"
           f"<body><div class='wrap'>{''.join(nav)}<main>{home}{''.join(sections)}</main></div>"
           f"<button class='toplink' title='Back to top'>&#8593;</button>"
           f"<script>{JS}</script></body></html>")
    out = DOCS / "Xon_Pipeline_Documentation.html"
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} ({len(doc)//1024} KB, self-contained, {len(PAGES)} pages)")


if __name__ == "__main__":
    build()
