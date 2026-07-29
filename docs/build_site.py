"""Build the HTML documentation site from the four markdown docs.

Produces docs/site/{index,1..4}.html — one linked, themed site with a sidebar, inline SVG
diagrams and schematics. Pure standard library (a small markdown subset renderer), so it
runs anywhere with no extra installs:

    python3 docs/build_site.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent
SITE = DOCS / "site"
SITE.mkdir(exist_ok=True)

PAGES = [
    ("index.html", "Overview", None),
    ("1_methods.html", "1 · Methods & Literature", "1_METHODS_AND_LITERATURE.md"),
    ("2_setup.html", "2 · Setup & Running", "2_SETUP_AND_RUNNING.md"),
    ("3_code.html", "3 · Code Walkthrough", "3_CODE_WALKTHROUGH.md"),
    ("4_outputs.html", "4 · Outputs & Analysis", "4_OUTPUTS_AND_ANALYSIS.md"),
]

CSS = """
:root{--red:#BA0C2F;--red-dk:#8f0a24;--ink:#1f2a33;--mut:#5b6770;--line:#e3e7eb;
--bg:#f7f8fa;--card:#fff;--blue:#2E5E8C;--gold:#D99A1C;--green:#1D7A74;--purple:#6A4C93}
*{box-sizing:border-box}
body{margin:0;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg)}
.wrap{display:flex;min-height:100vh;align-items:flex-start}
nav{width:290px;flex:0 0 290px;background:var(--card);border-right:1px solid var(--line);
padding:0 0 40px;position:sticky;top:0;height:100vh;overflow-y:auto}
nav .brand{background:var(--red);color:#fff;padding:20px 22px}
nav .brand b{display:block;font-size:1.05rem;letter-spacing:.2px}
nav .brand span{font-size:.8rem;opacity:.9}
nav a{display:block;padding:11px 22px;color:var(--ink);text-decoration:none;font-size:.93rem;
border-left:3px solid transparent}
nav a:hover{background:#f2f5f8}
nav a.active{background:#fdf2f4;border-left-color:var(--red);color:var(--red-dk);font-weight:600}
nav .sec{padding:16px 22px 6px;font-size:.72rem;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)}
nav .toc a{padding:6px 22px 6px 32px;font-size:.86rem;color:var(--mut);border-left:2px solid var(--line)}
nav .toc a:hover{color:var(--red-dk)}
main{flex:1;min-width:0;padding:44px 56px 90px;max-width:1080px}
h1{font-size:2.05rem;margin:.1em 0 .55em;letter-spacing:-.3px}
h2{font-size:1.42rem;margin:2.1em 0 .6em;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:1.12rem;margin:1.7em 0 .45em;color:var(--red-dk)}
h4{font-size:1rem;margin:1.3em 0 .35em}
p{margin:.7em 0}
code{background:#eef1f4;padding:2px 6px;border-radius:4px;font-size:.87em;
font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:#1f2a33;color:#e8eef3;padding:16px 18px;border-radius:9px;overflow-x:auto;
font-size:.86rem;line-height:1.5}
pre code{background:none;color:inherit;padding:0;font-size:inherit}
table{border-collapse:collapse;width:100%;margin:1.1em 0;font-size:.9rem;background:var(--card);
box-shadow:0 1px 2px rgba(0,0,0,.05);border-radius:8px;overflow:hidden}
th{background:#eef2f6;text-align:left;font-weight:650}
th,td{border:1px solid var(--line);padding:8px 11px;vertical-align:top}
tr:nth-child(even) td{background:#fafbfc}
blockquote{margin:1.1em 0;padding:12px 18px;background:#fff8e6;border-left:4px solid var(--gold);
border-radius:0 6px 6px 0}
blockquote p{margin:.3em 0}
ul,ol{margin:.6em 0;padding-left:1.5em}
li{margin:.28em 0}
hr{border:0;border-top:1px solid var(--line);margin:2.2em 0}
a{color:var(--red-dk)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(232px,1fr));gap:16px;margin:1.4em 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;
text-decoration:none;color:inherit;display:block;transition:.15s}
.card:hover{border-color:var(--red);box-shadow:0 4px 14px rgba(186,12,47,.11);transform:translateY(-2px)}
.card b{display:block;color:var(--red-dk);margin-bottom:5px;font-size:1.02rem}
.card span{font-size:.87rem;color:var(--mut)}
.hero{background:linear-gradient(135deg,var(--red),var(--red-dk));color:#fff;padding:34px 38px;
border-radius:12px;margin-bottom:26px}
.hero h1{color:#fff;margin:0 0 8px}
.hero p{margin:0;opacity:.94}
.fig{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;margin:1.5em 0;text-align:center}
.fig svg{max-width:100%;height:auto}
.fig figcaption{font-size:.84rem;color:var(--mut);margin-top:10px;font-style:italic}
.pill{display:inline-block;font-size:.74rem;font-weight:700;padding:2px 9px;border-radius:11px;
vertical-align:middle}
.on{background:#e3f5ec;color:#137a4d}.off{background:#fdeaea;color:#b3261e}
.always{background:#eef1f4;color:var(--mut)}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:1.3em 0}
.kpi div{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--blue);
border-radius:8px;padding:14px 16px}
.kpi b{display:block;font-size:1.5rem;color:var(--blue);line-height:1.2}
.kpi span{font-size:.8rem;color:var(--mut)}
@media(max-width:900px){.wrap{display:block}nav{width:auto;height:auto;position:static;flex:none}
main{padding:26px 20px}}
@media print{nav{display:none}main{padding:0;max-width:none}.card:hover{transform:none}}
"""

# ---------------------------------------------------------------- markdown subset
def md_inline(s: str) -> str:
    s = html.escape(s, quote=False)
    # Pull inline code out FIRST so its contents (which often contain * or _)
    # can't be swallowed by the emphasis patterns, then restore at the end.
    spans: list[str] = []

    def _stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    s = re.sub(r"`([^`]+)`", _stash, s)
    # ***bold+italic*** first, else the ** rule eats two of the three stars
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s)
    # non-greedy so **bold with *italic* inside** still matches; the (?!\*) stops the
    # closing ** from stealing two stars out of a trailing *** (…*italic*** case)
    s = re.sub(r"\*\*(.+?)\*\*(?!\*)", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    # links: [text](target)  — rewrite sibling .md links to their site pages
    def _link(m):
        text, href = m.group(1), m.group(2)
        for _pg, _t, src in PAGES:
            if src and (href.endswith(src) or href == src):
                href = _pg
                break
        return f'<a href="{href}">{text}</a>'
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, s)
    # ON/OFF pills
    s = s.replace("🟢", '<span class="pill on">ON</span>')
    s = s.replace("🔴", '<span class="pill off">OFF</span>')
    s = s.replace("⚙️", '<span class="pill always">ALWAYS</span>')
    # restore protected inline code
    s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
    return s


def slug(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    return re.sub(r"[\s_]+", "-", t)


def md_to_html(md: str):
    """Return (html, toc[(level,title,anchor)]). Supports headings, tables, lists,
    fenced code, blockquotes, hr, paragraphs — enough for these docs."""
    out, toc = [], []
    lines = md.split("\n")
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]

        if ln.startswith("```"):                                   # fenced code
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", ln)                     # headings
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
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table><thead><tr>"] + [f"<th>{md_inline(h)}</th>" for h in head] + ["</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        if re.match(r"^\s*>", ln):                                  # blockquote
            buf = []
            while i < n and re.match(r"^\s*>", lines[i]):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            inner, _ = md_to_html("\n".join(buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        if re.match(r"^\s*([-*+]|\d+\.)\s+", ln):                   # lists
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

        buf = [ln]; i += 1                                          # paragraph
        while i < n and lines[i].strip() and not re.match(
                r"^(\s*[-*+]\s|\s*\d+\.\s|#{1,4}\s|```|\s*\||\s*>)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append("<p>" + md_inline(" ".join(buf)) + "</p>")
    return "\n".join(out), toc


# ---------------------------------------------------------------- diagrams
def svg_flow() -> str:
    steps = [
        ("&#46;xdf file", "io_xdf&#46;py", "#5b6770"),
        ("Metadata", "metadata&#46;py", "#5b6770"),
        ("Preprocess", "filter &#183; bad channels", "#2E5E8C"),
        ("Channel screen", "ON by default", "#1D7A74"),
        ("Epoch + reject", "4 mechanisms", "#D99A1C"),
        ("Welch &#8594; FOOOF", "exponent", "#6A4C93"),
        ("Cohort report", "reporting/", "#BA0C2F"),
    ]
    w, h, bw, bh, gap = 980, 150, 124, 62, 14
    parts = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">']
    x, y = 6, 40
    for idx, (title, sub, col) in enumerate(steps):
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="9" fill="{col}"/>')
        parts.append(f'<text x="{x+bw/2}" y="{y+25}" text-anchor="middle" fill="#fff" '
                     f'font-size="13" font-weight="700">{title}</text>')
        parts.append(f'<text x="{x+bw/2}" y="{y+44}" text-anchor="middle" fill="#fff" '
                     f'font-size="10.5" opacity=".92">{sub}</text>')
        if idx < len(steps) - 1:
            ax = x + bw
            parts.append(f'<path d="M{ax+2} {y+bh/2} L{ax+gap-3} {y+bh/2}" stroke="#98a2ac" '
                         f'stroke-width="2" marker-end="url(#ah)"/>')
        x += bw + gap
    parts.insert(1, '<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" '
                    'orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#98a2ac"/></marker></defs>')
    parts.append(f'<text x="{w/2}" y="20" text-anchor="middle" fill="#1f2a33" font-size="12.5" '
                 f'font-weight="700">One recording, end to end</text>')
    parts.append(f'<text x="{w/2}" y="{y+bh+24}" text-anchor="middle" fill="#5b6770" font-size="11">'
                 f'PASS 2 re-runs the bracketed stages if a channel&#8217;s final exponent &lt; 0.5 '
                 f'&#8212; so the exponent we reject on is the exponent we report</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_reject() -> str:
    mech = [("Amplitude / flat", "&gt;100 &#181;V p-p", "#BA0C2F"),
            ("Gradient", "&gt;10 &#181;V/ms", "#D99A1C"),
            ("Variance z", "&gt; 3", "#2E5E8C"),
            ("Muscle z", "&gt; 3 on &gt;30 Hz", "#1D7A74")]
    w = 940
    parts = [f'<svg viewBox="0 0 {w} 236" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">']
    parts.append(f'<text x="{w/2}" y="18" text-anchor="middle" font-size="12.5" font-weight="700" '
                 f'fill="#1f2a33">Four rejection mechanisms &#8212; each hit attributed to the channel that caused it</text>')
    x = 20
    for name, thr, col in mech:
        parts.append(f'<rect x="{x}" y="36" width="200" height="58" rx="8" fill="{col}" opacity=".13" '
                     f'stroke="{col}" stroke-width="1.6"/>')
        parts.append(f'<text x="{x+100}" y="59" text-anchor="middle" font-size="12.5" font-weight="700" fill="{col}">{name}</text>')
        parts.append(f'<text x="{x+100}" y="78" text-anchor="middle" font-size="11" fill="#5b6770">{thr}</text>')
        parts.append(f'<path d="M{x+100} 96 L{x+100} 118" stroke="#98a2ac" stroke-width="1.8" marker-end="url(#ah2)"/>')
        x += 230
    parts.insert(1, '<defs><marker id="ah2" markerWidth="9" markerHeight="9" refX="7" refY="3" '
                    'orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#98a2ac"/></marker></defs>')
    parts.append('<rect x="20" y="120" width="900" height="52" rx="8" fill="#1f2a33"/>')
    parts.append('<text x="470" y="139" text-anchor="middle" font-size="12" fill="#fff">'
                 'Per-channel counters recorded in the master CSV</text>')
    parts.append('<text x="470" y="158" text-anchor="middle" font-size="11.5" fill="#9fd8c8" '
                 'font-family="ui-monospace,Menlo,Consolas,monospace">'
                 '{CH}_amp_flat_hits &#183; _gradient_hits &#183; _variance_hits &#183; _muscle_hits</text>')
    parts.append('<path d="M470 174 L470 190" stroke="#98a2ac" stroke-width="1.8" marker-end="url(#ah2)"/>')
    parts.append('<rect x="230" y="192" width="480" height="38" rx="8" fill="#BA0C2F"/>')
    parts.append('<text x="470" y="216" text-anchor="middle" font-size="12.5" fill="#fff" font-weight="700">'
                 'worst_reject_channel &#183; worst_reject_channel_share</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_montage() -> str:
    coords = {"Fp1": (-.31, .95), "Fp2": (.31, .95), "F7": (-.81, .59), "F3": (-.41, .61),
              "Fz": (0, .63), "F4": (.41, .61), "F8": (.81, .59), "T7": (-1, 0), "C3": (-.5, 0),
              "Cz": (0, 0), "C4": (.5, 0), "T8": (1, 0), "P7": (-.81, -.59), "P3": (-.41, -.61),
              "Pz": (0, -.63), "P4": (.41, -.61), "P8": (.81, -.59), "O1": (-.31, -.95), "O2": (.31, -.95)}
    reg = {"F3": "#6A4C93", "F4": "#6A4C93", "C3": "#1D7A74", "C4": "#1D7A74", "Cz": "#1D7A74",
           "P3": "#A63A50", "P4": "#A63A50"}
    R, cx, cy = 132, 175, 175
    p = ['<svg viewBox="0 0 350 400" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">']
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#1f2a33" stroke-width="3"/>')
    p.append(f'<path d="M{cx-15} {cy-R+2} L{cx} {cy-R-18} L{cx+15} {cy-R+2}" fill="none" stroke="#1f2a33" stroke-width="3" stroke-linejoin="round"/>')
    for ch, (ux, uy) in coords.items():
        X, Y = cx + ux * R, cy - uy * R
        if ch in reg:
            p.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="19" fill="{reg[ch]}" stroke="#fff" stroke-width="2.5"/>')
            p.append(f'<text x="{X:.1f}" y="{Y+4.5:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">{ch}</text>')
        else:
            p.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="14" fill="#eef0f2" stroke="#c3c7cc" stroke-width="1.3"/>')
            p.append(f'<text x="{X:.1f}" y="{Y+3.5:.1f}" text-anchor="middle" font-size="9" fill="#aeb4ba">{ch}</text>')
    ly = 330
    for lbl, col in [("Frontal (F3, F4)", "#6A4C93"), ("Central (C3, C4, Cz)", "#1D7A74"),
                     ("Parietal (P3, P4)", "#A63A50")]:
        p.append(f'<rect x="60" y="{ly-10}" width="15" height="15" rx="3" fill="{col}"/>')
        p.append(f'<text x="84" y="{ly+2}" font-size="12" fill="#1f2a33">{lbl}</text>')
        ly += 22
    p.append("</svg>")
    return "".join(p)


def svg_minutes() -> str:
    w, h = 900, 268
    p = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial">']
    p.append(f'<text x="{w/2}" y="18" text-anchor="middle" font-size="12.5" font-weight="700" fill="#1f2a33">'
             'Two different &#8220;how many minutes are enough?&#8221; questions</text>')
    x0, x1, ax = 70, 830, 150
    p.append(f'<line x1="{x0}" y1="{ax}" x2="{x1}" y2="{ax}" stroke="#98a2ac" stroke-width="2"/>')
    for mins in range(0, 31, 5):
        X = x0 + (x1 - x0) * mins / 30
        p.append(f'<line x1="{X}" y1="{ax-4}" x2="{X}" y2="{ax+4}" stroke="#98a2ac" stroke-width="1.5"/>')
        p.append(f'<text x="{X}" y="{ax+20}" text-anchor="middle" font-size="10.5" fill="#5b6770">{mins}</text>')
    p.append(f'<text x="{(x0+x1)/2}" y="{ax+40}" text-anchor="middle" font-size="11.5" fill="#5b6770">clean minutes</text>')
    # reliability marker ~1 min
    Xr = x0 + (x1 - x0) * 1 / 30
    p.append(f'<line x1="{Xr}" y1="{ax}" x2="{Xr}" y2="60" stroke="#1D7A74" stroke-width="2.5"/>')
    p.append(f'<circle cx="{Xr}" cy="60" r="6" fill="#1D7A74"/>')
    p.append(f'<text x="{Xr+12}" y="52" font-size="12" font-weight="700" fill="#1D7A74">~1 min</text>')
    p.append(f'<text x="{Xr+12}" y="68" font-size="11" fill="#5b6770">Reliability (rank-ordering people) is reached</text>')
    # stabilize 14.25
    Xs = x0 + (x1 - x0) * 14.25 / 30
    p.append(f'<line x1="{Xs}" y1="{ax}" x2="{Xs}" y2="98" stroke="#D99A1C" stroke-width="2.5"/>')
    p.append(f'<circle cx="{Xs}" cy="98" r="6" fill="#D99A1C"/>')
    p.append(f'<text x="{Xs+12}" y="94" font-size="12" font-weight="700" fill="#D99A1C">14.25 min &#8212; median precise</text>')
    p.append(f'<text x="{Xs+12}" y="110" font-size="11" fill="#5b6770">odd/even halves agree (minutes_to_stabilize)</text>')
    # converge 17
    Xc = x0 + (x1 - x0) * 17 / 30
    p.append(f'<line x1="{Xc}" y1="{ax}" x2="{Xc}" y2="128" stroke="#BA0C2F" stroke-width="2.5"/>')
    p.append(f'<circle cx="{Xc}" cy="128" r="6" fill="#BA0C2F"/>')
    p.append(f'<text x="{Xc+12}" y="132" font-size="12" font-weight="700" fill="#BA0C2F">17 min &#8212; median full value</text>')
    p.append(f'<text x="{Xc+12}" y="148" font-size="11" fill="#5b6770">(minutes_to_converge)</text>')
    p.append(f'<rect x="{x0}" y="204" width="{x1-x0}" height="48" rx="8" fill="#fff8e6" stroke="#D99A1C"/>')
    p.append(f'<text x="{(x0+x1)/2}" y="224" text-anchor="middle" font-size="12" font-weight="700" fill="#1f2a33">'
             'Short data ranks people reliably; the absolute value keeps drifting for 10&#8211;17 min.</text>')
    p.append(f'<text x="{(x0+x1)/2}" y="242" text-anchor="middle" font-size="11.5" fill="#5b6770">'
             'A short recording can be precise but biased LOW.</text>')
    p.append("</svg>")
    return "".join(p)


DIAGRAMS = {
    "1_methods.html": [("## 1.7", svg_minutes(),
                        "The two distinct duration questions, on one axis (cohort medians).")],
    "3_code.html": [("## The flow, end to end", svg_flow(),
                     "Module-by-module flow for a single recording."),
                    ("### `reject_artifacts()`", svg_reject(),
                     "Rejection mechanisms and the per-channel attribution they feed.")],
    "4_outputs.html": [("### Scalp region", svg_montage(),
                        "The 7 Xon electrodes on the 10-20 layout, coloured by region.")],
}


def shell(page: str, title: str, body: str, toc) -> str:
    nav = ['<nav><div class="brand"><b>Xon Aperiodic Pipeline</b><span>Documentation</span></div>']
    nav.append('<div class="sec">Contents</div>')
    for fn, t, _ in PAGES:
        cls = ' class="active"' if fn == page else ""
        nav.append(f'<a href="{fn}"{cls}>{t}</a>')
        if fn == page and toc:
            nav.append('<div class="toc">')
            for lvl, txt, anc in toc:
                if lvl == 2:
                    nav.append(f'<a href="#{anc}">{html.escape(txt)}</a>')
            nav.append("</div>")
    nav.append('<div class="sec">Repo</div>')
    nav.append('<a href="../../README.md">README</a>')
    nav.append('<a href="../archive/">Archived docs</a>')
    nav.append("</nav>")
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)} — Xon Aperiodic Pipeline</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'>{''.join(nav)}<main>{body}</main></div></body></html>")


def build_single():
    """One fully self-contained HTML file: all four docs + overview, in-page navigation,
    inline CSS and inline SVG. No sibling files, no internet, no repo needed — it can be
    emailed on its own and will work anywhere."""
    sections, navlinks = [], []
    for page, title, src in PAGES:
        if src is None:
            continue
        pid = page.replace(".html", "")
        md = (DOCS / src).read_text(encoding="utf-8")
        body, toc = md_to_html(md)
        # namespace anchors so the four docs can't collide in one document
        body = re.sub(r'(<h[1-4]) id="([^"]*)"', rf'\1 id="{pid}--\2"', body)
        # diagrams
        for anchor, svg, cap in DIAGRAMS.get(page, []):
            m = re.match(r"^(#+)\s+(.*)$", anchor)
            lvl, prefix = len(m.group(1)), m.group(2).strip()
            fig = f'<figure class="fig">{svg}<figcaption>{cap}</figcaption></figure>'
            for hm in re.finditer(rf'<h{lvl} id="[^"]*">(.*?)</h{lvl}>', body, re.S):
                plain = re.sub(r"<[^>]+>", "", hm.group(1)).replace("&amp;", "&").strip()
                if plain.startswith(prefix.replace("`", "")):
                    body = body[:hm.end()] + fig + body[hm.end():]
                    break
        # cross-document links become in-page jumps
        for pg2, _t2, src2 in PAGES:
            if src2:
                body = body.replace(f'href="{pg2}"', f'href="#{pg2.replace(".html","")}"')
        sections.append(f'<section id="{pid}">{body}</section>')
        subs = "".join(f'<a href="#{pid}--{a}">{html.escape(t)}</a>'
                       for lvl, t, a in toc if lvl == 2)
        navlinks.append((pid, title, subs))

    nav = ['<nav><div class="brand"><b>Xon Aperiodic Pipeline</b>'
           '<span>Complete documentation &mdash; single file</span></div>',
           '<div class="sec">Contents</div>',
           '<a href="#top">Overview</a>']
    for pid, title, subs in navlinks:
        nav.append(f'<a href="#{pid}">{title}</a>')
        if subs:
            nav.append(f'<div class="toc">{subs}</div>')
    nav.append("</nav>")

    cards = "".join(
        f'<a class="card" href="#{i}"><b>{t}</b><span>{d}</span></a>'
        for i, t, d in [
            ("1_methods", "1 · Methods & Literature",
             "Why every setting is what it is — with the papers behind it."),
            ("2_setup", "2 · Setup & Running",
             "Install, run and troubleshoot. Non-coder and coder tracks."),
            ("3_code", "3 · Code Walkthrough",
             "Every module and function; what it does and whether it's ON by default."),
            ("4_outputs", "4 · Outputs & Analysis",
             "Every output file, every analysis, and the full master-CSV dictionary."),
        ])
    overview = f"""<section id="top">
<div class="hero"><h1>Xon Aperiodic Pipeline</h1>
<p>Turning 7-channel Xon <code>.xdf</code> recordings into the EEG aperiodic exponent —
reliably, reproducibly, and offline. <b>This single file contains the complete
documentation</b>; nothing else is required to read it.</p></div>
<div class="kpi">
  <div><b>39</b><span>recordings processed</span></div>
  <div><b>0.98</b><span>mean fit r&sup2;</span></div>
  <div><b>0.90</b><span>rest test–retest ICC</span></div>
  <div><b>14.25</b><span>median min to stabilize</span></div>
</div>
<h2 id="top--start">Start here</h2>
<div class="cards">{cards}</div>
<figure class="fig">{svg_flow()}<figcaption>How one recording moves through the pipeline.</figcaption></figure>
<h2 id="top--quick">The 60-second version</h2>
<ul>
<li><b>Run it:</b> double-click <code>Start Here (Mac).command</code> or
<code>Start Here (Windows).bat</code>, pick an input and an output folder, press Run.</li>
<li><b>Read it:</b> open <code>cohort_report.html</code> in the output folder.</li>
<li><b>Analyse it:</b> <code>master_everything.csv</code> — one wide row per recording,
163 columns, including <i>why</i> each channel caused rejections.</li>
<li><b>Change it:</b> everything lives in <code>config/config.yaml</code>, or tick it in the GUI.</li>
</ul>
<blockquote><p><b>The one caveat to remember:</b> this pilot establishes
<b>reliability and consistency</b>, not absolute accuracy — no simultaneous research-grade
EEG reference was recorded.</p></blockquote>
</section>"""

    extra = ("<style>section{scroll-margin-top:12px}"
             "section+section{border-top:3px solid var(--line);margin-top:56px;padding-top:34px}"
             "@media print{section+section{page-break-before:always;border-top:0}}</style>")
    doc = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Xon Aperiodic Pipeline — Complete Documentation</title>"
           f"<style>{CSS}</style>{extra}</head><body><div class='wrap'>"
           f"{''.join(nav)}<main>{overview}{''.join(sections)}</main></div></body></html>")
    out = DOCS / "Xon_Pipeline_Documentation.html"
    out.write_text(doc, encoding="utf-8")
    print("wrote", out, f"({len(doc)//1024} KB, fully self-contained)")


def build():
    for page, title, src in PAGES:
        if src is None:
            continue
        md = (DOCS / src).read_text(encoding="utf-8")
        body, toc = md_to_html(md)
        for anchor, svg, cap in DIAGRAMS.get(page, []):
            m = re.match(r"^(#+)\s+(.*)$", anchor)
            if not m:
                continue
            lvl, prefix = len(m.group(1)), m.group(2).strip()
            # find the heading of this level whose *text* starts with the given prefix
            fig = f'<figure class="fig">{svg}<figcaption>{cap}</figcaption></figure>'
            placed = False
            for hm in re.finditer(rf'<h{lvl} id="[^"]*">(.*?)</h{lvl}>', body, re.S):
                plain = re.sub(r"<[^>]+>", "", hm.group(1))
                plain = plain.replace("&amp;", "&").strip()
                if plain.startswith(prefix.replace("`", "")):
                    body = body[:hm.end()] + fig + body[hm.end():]
                    placed = True
                    break
            if not placed:
                raise SystemExit(f"DIAGRAM ANCHOR NOT FOUND in {page}: {anchor!r}")
        (SITE / page).write_text(shell(page, title, body, toc), encoding="utf-8")
        print("wrote", SITE / page)

    cards = "".join(
        f'<a class="card" href="{fn}"><b>{t}</b><span>{d}</span></a>'
        for fn, t, d in [
            ("1_methods.html", "1 · Methods & Literature",
             "Why every setting is what it is — with the papers behind it."),
            ("2_setup.html", "2 · Setup & Running",
             "Install, run and troubleshoot. Non-coder and coder tracks."),
            ("3_code.html", "3 · Code Walkthrough",
             "Every module and function; what it does and whether it's ON by default."),
            ("4_outputs.html", "4 · Outputs & Analysis",
             "Every output file, every analysis, and the full master-CSV dictionary."),
        ])
    idx_body = f"""
<div class="hero"><h1>Xon Aperiodic Pipeline</h1>
<p>Turning 7-channel Xon <code>.xdf</code> recordings into the EEG aperiodic exponent —
reliably, reproducibly, and offline.</p></div>
<div class="kpi">
  <div><b>39</b><span>recordings processed</span></div>
  <div><b>0.98</b><span>mean fit r&sup2;</span></div>
  <div><b>0.90</b><span>rest test–retest ICC</span></div>
  <div><b>14.25</b><span>median min to stabilize</span></div>
</div>
<h2 id="start">Start here</h2>
<div class="cards">{cards}</div>
<figure class="fig">{svg_flow()}<figcaption>How one recording moves through the pipeline.</figcaption></figure>
<h2 id="quick">The 60-second version</h2>
<ul>
<li><b>Run it:</b> double-click <code>Start Here (Mac).command</code> or
<code>Start Here (Windows).bat</code>, pick an input and an output folder, press Run.</li>
<li><b>Read it:</b> open <code>cohort_report.html</code> in the output folder.</li>
<li><b>Analyse it:</b> <code>master_everything.csv</code> — one wide row per recording,
163 columns, including <i>why</i> each channel caused rejections.</li>
<li><b>Change it:</b> everything lives in <code>config/config.yaml</code>, or tick it in the GUI.</li>
</ul>
<blockquote><p><b>The one caveat to remember:</b> this pilot establishes
<b>reliability and consistency</b>, not absolute accuracy — no simultaneous research-grade
EEG reference was recorded.</p></blockquote>
<h2 id="map">Where things live</h2>
<table><thead><tr><th>Path</th><th>What</th></tr></thead><tbody>
<tr><td><code>config/config.yaml</code></td><td>every setting, commented</td></tr>
<tr><td><code>src/xon_aperiodic/</code></td><td>the pipeline modules</td></tr>
<tr><td><code>docs/</code></td><td>these four documents (<code>archive/</code> = superseded)</td></tr>
<tr><td><code>tests/</code></td><td>13 synthetic tests — no patient data</td></tr>
<tr><td><code>update.py</code></td><td>updates that preserve local edits</td></tr>
</tbody></table>
"""
    (SITE / "index.html").write_text(shell("index.html", "Overview", idx_body, []), encoding="utf-8")
    print("wrote", SITE / "index.html")


if __name__ == "__main__":
    build()          # docs/site/  — the linked multi-page version
    build_single()   # docs/Xon_Pipeline_Documentation.html — one shareable file
