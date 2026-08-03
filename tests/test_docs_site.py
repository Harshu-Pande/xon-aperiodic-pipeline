"""The documentation site's JavaScript must actually run.

This exists because of a bug that shipped in two repos and went unnoticed for weeks:

    const top = document.querySelector('.toplink');

At the top level of a classic script, ``top`` is already a property of ``window`` (the
top-level browsing context), so this throws

    SyntaxError: Identifier 'top' has already been declared

The failure mode is what made it slippery. A SyntaxError is raised while *parsing* the
script, so NOTHING in it ever runs - not the sidebar, not the search, not the in-page
links - and the page still renders perfectly, because the HTML and CSS are fine. There is
no visible error unless you open the developer console. The docs simply feel broken.

So these tests check the two things a reader actually does: click a sidebar entry, and
search. They run the real generated file in a real DOM when jsdom is available, and fall
back to static checks (which would have caught this particular bug on their own) when it
is not.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "docs" / "build_site.py"

# Every name that already exists as a property of `window`. Declaring any of them with
# const/let at the top level of a classic script is a SyntaxError that kills the file.
WINDOW_GLOBALS = [
    "top", "name", "status", "length", "closed", "parent", "self", "history",
    "origin", "location", "frames", "event", "external", "screen", "menubar",
]


@pytest.fixture(scope="module")
def site_html(tmp_path_factory) -> str:
    """Build the docs site exactly as `python3 docs/build_site.py` does."""
    if not BUILDER.exists():
        pytest.skip("docs/build_site.py not present")
    out = ROOT / "docs" / "Xon_Pipeline_Documentation.html"
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True,
                   capture_output=True)
    assert out.exists(), "the builder did not write the HTML file"
    return out.read_text(encoding="utf-8")


def _script(html: str) -> str:
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert blocks, "the page has no <script> block"
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# static checks - cheap, no node required, and enough to catch the shipped bug
# ---------------------------------------------------------------------------
def test_script_does_not_redeclare_a_window_global(site_html):
    """`const top = ...` at top level is a SyntaxError that silently kills the page."""
    js = _script(site_html)
    offenders = [g for g in WINDOW_GLOBALS
                 if re.search(rf"^\s*(?:const|let|class)\s+{g}\b", js, re.M)]
    assert not offenders, (
        f"top-level declaration(s) of window global(s) {offenders}. This throws "
        "'Identifier ... has already been declared' and stops the ENTIRE script, so the "
        "sidebar and search stop working with no visible error. Rename them, or keep the "
        "code inside the IIFE where shadowing is legal.")


def test_script_is_wrapped_so_a_stray_name_cannot_break_the_page(site_html):
    js = _script(site_html).strip()
    assert js.startswith("(function(){"), (
        "the page script must stay inside an IIFE - at top level, one unlucky variable "
        "name takes the whole page down")
    assert "'use strict'" in js


def test_history_replacestate_is_guarded_for_file_urls(site_html):
    """These docs are opened straight off disk; some browsers throw a SecurityError on
    history.replaceState for a file:// URL."""
    js = _script(site_html)
    m = re.search(r"try\s*\{[^}]*history\.replaceState", js)
    assert m, "history.replaceState must be inside a try/catch (file:// throws)"


def test_every_sidebar_link_points_at_a_page_that_exists(site_html):
    pages = set(re.findall(r'id="(page-[^"]+)"', site_html))
    targets = {f"page-{p}" for p in re.findall(r'class="navlink" data-page="([^"]+)"',
                                               site_html)}
    assert targets, "no sidebar links found"
    assert targets <= pages, f"sidebar points at missing page(s): {targets - pages}"


# ---------------------------------------------------------------------------
# the real thing: run the page in a DOM and click
# ---------------------------------------------------------------------------
def _jsdom_env():
    """Return an env that can `require('jsdom')`, or None.

    jsdom is a dev convenience, not a dependency of this project - so it may live in any
    of a few places, or nowhere. When it is absent this test skips and the static checks
    above carry the load; they would have caught the shipped bug on their own.
    """
    import os
    if not shutil.which("node"):
        return None
    roots = [r for r in (os.environ.get("NODE_PATH"), "/tmp/node_modules",
                         str(Path.home() / "node_modules"),
                         str(ROOT / "node_modules")) if r]
    for root in roots:
        env = dict(os.environ, NODE_PATH=root)
        # Probe from "/" so that node's cwd-relative lookup cannot mask a NODE_PATH that
        # will not work later: node resolves modules from the SCRIPT's directory, and the
        # driver below is written into a pytest tmp dir, not next to node_modules.
        if subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True,
                          env=env, cwd="/").returncode == 0:
            return env
    return None


_JSDOM_ENV = _jsdom_env()


@pytest.mark.skipif(_JSDOM_ENV is None, reason="node + jsdom not available")
def test_clicking_the_sidebar_and_searching_actually_navigate(site_html, tmp_path):
    """The two things a reader does. Runs the generated file in a real DOM."""
    page = tmp_path / "docs.html"
    page.write_text(site_html, encoding="utf-8")
    driver = tmp_path / "drive.js"
    driver.write_text(textwrap.dedent("""
        const fs = require('fs');
        const { JSDOM } = require('jsdom');
        const errs = [];
        const dom = new JSDOM(fs.readFileSync(process.argv[2], 'utf8'), {
          runScripts: 'dangerously', url: 'file:///docs.html',
          beforeParse(w) {
            w.addEventListener('error', e => errs.push(e.message));
            w.scrollTo = () => {};
            w.Element.prototype.scrollIntoView = function () {};
          },
        });
        const w = dom.window, d = w.document;
        const click = el => el.dispatchEvent(
          new w.MouseEvent('click', {bubbles: true, cancelable: true}));
        setTimeout(() => {
          const nav = {};
          for (const l of d.querySelectorAll('.navlink')) {
            click(l);
            nav[l.dataset.page] = (d.querySelector('.page.active') || {}).id;
          }
          const box = d.getElementById('q'), res = d.getElementById('qres');
          box.value = 'artifact';
          box.dispatchEvent(new w.Event('input', {bubbles: true}));
          const hits = [...res.querySelectorAll('a')];
          let afterSearch = null;
          if (hits.length) { click(hits[0]);
            afterSearch = (d.querySelector('.page.active') || {}).id; }
          console.log(JSON.stringify({errors: errs, nav, hits: hits.length, afterSearch}));
        }, 400);
    """), encoding="utf-8")

    out = subprocess.run(["node", str(driver), str(page)], capture_output=True,
                         text=True, cwd="/tmp", timeout=120, env=_JSDOM_ENV)
    assert out.returncode == 0, out.stderr[-2000:]
    r = json.loads(out.stdout.strip().splitlines()[-1])

    assert not r["errors"], f"the page threw at runtime: {r['errors']}"
    for want, got in r["nav"].items():
        assert got == f"page-{want}", (
            f"clicking the '{want}' sidebar link left page '{got}' showing")
    assert r["hits"] > 0, "searching for 'artifact' found nothing in the docs"
    assert r["afterSearch"], "clicking a search result did not switch page"
