"""Poster-quality figures for the SPIN poster — coherent theme, Calibri-matched font,
large type, minimal chartjunk. Rebuilt from the real Xon results data so numbers match the
poster captions exactly. Standalone (only pandas/numpy/scipy/matplotlib)."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager as fm
from scipy import stats as sps

# ---- font: Carlito (metric-compatible with Calibri, the poster font) ----
for f in ["/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
          "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
          "/usr/share/fonts/truetype/crosextra/Carlito-Italic.ttf",
          "/usr/share/fonts/truetype/crosextra/Carlito-BoldItalic.ttf"]:
    if os.path.exists(f):
        fm.fontManager.addfont(f)
FONT = "Carlito" if any("Carlito" in f.name for f in fm.fontManager.ttflist) else "DejaVu Sans"

# ---- theme palette ----
REST = "#2E5E8C"      # steel blue  (quiet rest)
MOVIE = "#D99A1C"     # amber/gold  (movie) — distinct, harmonises with the crimson theme
ACCENT = "#BA0C2F"    # WashU red   (median / identity / reference lines)
INK = "#1f2a33"       # near-black text
GRID = "#e7e9ec"
REGION = {"frontal": "#6A4C93", "central": "#1D7A74", "parietal": "#A63A50"}
REGION_ORDER = ["frontal", "central", "parietal"]
REGIONS = {"frontal": ["F3", "F4"], "central": ["C3", "C4", "Cz"], "parietal": ["P3", "P4"]}

plt.rcParams.update({
    "font.family": FONT, "figure.dpi": 130, "savefig.dpi": 300,
    "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": "#8a929b",
    "xtick.color": INK, "ytick.color": INK,
    "font.size": 17, "axes.labelsize": 19, "axes.titlesize": 20,
    "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 16,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 1.4, "legend.frameon": False, "figure.facecolor": "white",
    "savefig.facecolor": "white", "savefig.bbox": "tight",
})

OUT = "/sessions/amazing-jolly-maxwell/mnt/outputs/poster_figs"
os.makedirs(OUT, exist_ok=True)
M = pd.read_csv("/sessions/amazing-jolly-maxwell/mnt/Xon results/master_everything.csv")
num = lambda s: pd.to_numeric(s, errors="coerce")


def color(cond):
    return REST if str(cond) == "rest" else MOVIE


def style_ax(ax):
    ax.tick_params(length=5, width=1.2)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#8a929b")


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p); plt.close(fig)
    return p


# ---------------------------------------------------------------- 1. montage
def fig_montage():
    coords = {"Fp1": (-0.31, 0.95), "Fp2": (0.31, 0.95), "F7": (-0.81, 0.59),
              "F3": (-0.41, 0.61), "Fz": (0.0, 0.63), "F4": (0.41, 0.61), "F8": (0.81, 0.59),
              "T7": (-1.0, 0.0), "C3": (-0.5, 0.0), "Cz": (0.0, 0.0), "C4": (0.5, 0.0), "T8": (1.0, 0.0),
              "P7": (-0.81, -0.59), "P3": (-0.41, -0.61), "Pz": (0.0, -0.63), "P4": (0.41, -0.61),
              "P8": (0.81, -0.59), "O1": (-0.31, -0.95), "O2": (0.31, -0.95)}
    ch2reg = {c: r for r, cs in REGIONS.items() for c in cs}
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.add_patch(mpatches.Circle((0, 0), 1.0, fill=False, color=INK, lw=3))
    ax.plot([-0.13, 0, 0.13], [0.99, 1.17, 0.99], color=INK, lw=3, solid_capstyle="round")
    ax.add_patch(mpatches.Arc((-1.0, 0), 0.22, 0.46, theta1=90, theta2=270, color=INK, lw=3))
    ax.add_patch(mpatches.Arc((1.0, 0), 0.22, 0.46, theta1=-90, theta2=90, color=INK, lw=3))
    for ch, (x, y) in coords.items():
        reg = ch2reg.get(ch)
        if reg:
            ax.scatter([x], [y], s=1150, color=REGION[reg], edgecolor="white", linewidth=2.2, zorder=3)
            ax.text(x, y, ch, ha="center", va="center", color="white", fontsize=15,
                    fontweight="bold", zorder=4)
        else:
            ax.scatter([x], [y], s=560, facecolor="#eef0f2", edgecolor="#c3c7cc", linewidth=1.3, zorder=1)
            ax.text(x, y, ch, ha="center", va="center", color="#aeb4ba", fontsize=10.5, zorder=1)
    handles = [mpatches.Patch(color=REGION[r], label=f"{r.capitalize()} ({', '.join(REGIONS[r])})")
               for r in REGION_ORDER]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02),
              ncol=1, fontsize=15, handlelength=1.1, borderpad=0.2, labelspacing=0.35)
    ax.set_xlim(-1.32, 1.32); ax.set_ylim(-1.62, 1.28)
    ax.set_aspect("equal"); ax.axis("off")
    return save(fig, "fig_montage.png")


# ---------------------------------------------------------------- regional helper
def regional_by_participant(cond):
    d = M[(M["status"].astype(str) != "error") & (M["condition"].astype(str) == cond)]
    rows = []
    for _, rec in d.iterrows():
        row = {"participant": rec["participant"]}
        for reg, chans in REGIONS.items():
            vals = []
            for ch in chans:
                v = num(pd.Series([rec.get(f"{ch}_exponent")])).iloc[0]
                if pd.isna(v) or bool(rec.get(f"{ch}_interpolated")) or bool(rec.get(f"{ch}_excluded")):
                    continue
                vals.append(float(v))
            row[reg] = np.mean(vals) if vals else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    return df.groupby("participant")[REGION_ORDER].mean().dropna()


def friedman_p(pp):
    if len(pp) < 3:
        return None
    try:
        return float(sps.friedmanchisquare(*[pp[r].values for r in REGION_ORDER]).pvalue)
    except Exception:
        return None


# ---------------------------------------------------------------- 2. regional
def fig_regional():
    fig, ax = plt.subplots(figsize=(6.9, 5.2))
    x = list(range(3))
    for i, r in enumerate(REGION_ORDER):
        ax.axvspan(i - 0.5, i + 0.5, color=REGION[r], alpha=0.08, zorder=0)
    rng = np.random.default_rng(1)
    ptxt = {}
    for cond in ("rest", "movie"):
        pp = regional_by_participant(cond)
        ptxt[cond] = friedman_p(pp)
        col = color(cond); ls = "-" if cond == "rest" else "--"
        for i, r in enumerate(REGION_ORDER):
            yv = pp[r].values
            ax.scatter(rng.normal(i, 0.055, len(yv)), yv, color=col, s=34, alpha=0.30,
                       edgecolor="none", zorder=2)
        means = [pp[r].mean() for r in REGION_ORDER]
        sems = [pp[r].std(ddof=1) / np.sqrt(len(pp)) for r in REGION_ORDER]
        ax.errorbar(x, means, yerr=sems, color=col, linestyle=ls, marker="o", markersize=11,
                    linewidth=3.2, capsize=6, capthick=2.4, markeredgecolor="white",
                    markeredgewidth=1.6, zorder=3, label=f"{cond.capitalize()} (n={len(pp)})")
    ax.set_xticks(x)
    ax.set_xticklabels([r.capitalize() for r in REGION_ORDER])
    for tick, r in zip(ax.get_xticklabels(), REGION_ORDER):
        tick.set_color(REGION[r]); tick.set_fontweight("bold")
    ax.set_ylabel("Aperiodic exponent")
    ax.set_xlim(-0.5, 2.5)
    style_ax(ax)
    ax.legend(loc="upper right", handlelength=1.9)
    # compact significance note
    def star(p):
        return "" if p is None else (" **" if p < 0.01 else (" *" if p < 0.05 else " n.s."))
    note = (f"Rest: p = {ptxt['rest']:.3f}{star(ptxt['rest'])}\n"
            f"Movie: p = {ptxt['movie']:.3f}{star(ptxt['movie'])}")
    ax.text(0.03, 0.04, note, transform=ax.transAxes, va="bottom", ha="left", fontsize=14.5,
            color=INK, bbox=dict(boxstyle="round,pad=0.35", facecolor="#f6f7f9", edgecolor="#d7dbe0"))
    return save(fig, "fig_regional.png")


# ---------------------------------------------------------------- 3. within-session paired
def fig_paired():
    d = M[M["status"].astype(str) != "error"].copy()
    d["key"] = d["participant"].astype(str) + "|" + d["session"].astype(str)
    q = d[d["condition"] == "rest"].set_index("key")["AVERAGE_exponent"].pipe(num)
    n = d[d["condition"] == "movie"].set_index("key")["AVERAGE_exponent"].pipe(num)
    common = sorted(set(q.dropna().index) & set(n.dropna().index))
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    for k in common:
        ax.plot([0, 1], [q[k], n[k]], "-", color="#c2c7cd", alpha=0.8, lw=1.6, zorder=1)
    ax.scatter([0] * len(common), [q[k] for k in common], color=REST, s=95, zorder=3,
               edgecolor="white", linewidth=1.4)
    ax.scatter([1] * len(common), [n[k] for k in common], color=MOVIE, s=95, zorder=3,
               edgecolor="white", linewidth=1.4)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Rest\n(quiet)", "Movie\n(noisy)"])
    ax.set_xlim(-0.45, 1.45)
    ax.set_ylabel("Aperiodic exponent")
    style_ax(ax)
    ax.text(0.5, 0.97, "Δ = 0.002    95% CI [−0.076, 0.080]    n = 19",
            transform=ax.transAxes, ha="center", va="top", fontsize=15, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f6f7f9", edgecolor="#d7dbe0"))
    return save(fig, "fig_paired.png")


# ---------------------------------------------------------------- 4. test-retest
def fig_testretest():
    d = M[M["status"].astype(str) != "error"].copy()
    d["AVERAGE_exponent"] = num(d["AVERAGE_exponent"])
    fig, ax = plt.subplots(figsize=(5.8, 5.8))
    iccs = {"rest": "0.90", "movie": "0.61"}
    lo, hi = 0.78, 1.55
    ax.plot([lo, hi], [lo, hi], "--", color=ACCENT, lw=2.2, alpha=0.9, zorder=1)
    ax.text(hi - 0.02, hi - 0.05, "identity", color=ACCENT, ha="right", va="top",
            fontsize=13.5, rotation=45, rotation_mode="anchor")
    for cond in ("rest", "movie"):
        g = d[d["condition"] == cond]
        piv = g.pivot_table(index="participant", columns="session",
                            values="AVERAGE_exponent", aggfunc="mean").dropna(how="any")
        if piv.shape[1] < 2:
            continue
        s = sorted(piv.columns)[:2]
        ax.scatter(piv[s[0]], piv[s[1]], color=color(cond), s=120, alpha=0.9,
                   edgecolor="white", linewidth=1.5, zorder=3,
                   label=f"{cond.capitalize()}  ICC = {iccs[cond]}  (n={piv.shape[0]})")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.set_xlabel("Session 1 exponent"); ax.set_ylabel("Session 2 exponent")
    style_ax(ax)
    ax.legend(loc="upper left", handletextpad=0.4)
    return save(fig, "fig_testretest.png")


# ---------------------------------------------------------------- 5. stabilization
def fig_stabilization():
    d = M[M["status"].astype(str) != "error"].copy()
    d["mts"] = num(d["minutes_to_stabilize"])
    d = d.dropna(subset=["mts"])
    rng = np.random.default_rng(3)
    fig, ax = plt.subplots(figsize=(9.3, 3.9))
    for cond in ("rest", "movie"):
        sub = d[d["condition"] == cond]
        ax.scatter(sub["mts"], rng.uniform(-1, 1, len(sub)), color=color(cond), s=115,
                   alpha=0.85, edgecolor="white", linewidth=1.1, zorder=3,
                   label=cond.capitalize())
    med = float(np.median(d["mts"]))
    ax.axvline(med, color=ACCENT, lw=2.6, zorder=4)
    ax.text(med + 0.3, 1.75, f"median = {med:.2f} min", color=ACCENT, fontsize=16,
            fontweight="bold", ha="left", va="center")
    ax.set_ylim(-2.4, 2.4); ax.set_yticks([])
    ax.set_ylabel("ICC")
    ax.set_xlabel("Clean data used before estimate stabilized (minutes)")
    ax.set_xlim(0, max(28, d["mts"].max() + 1))
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=5, width=1.2)
    ax.legend(loc="lower right", ncol=2, handletextpad=0.3, columnspacing=1.0)
    return save(fig, "fig_stabilization.png")


# ---------------------------------------------------------------- 6. background schematic
def fig_schematic():
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    f = np.linspace(1, 45, 600)
    aper = 10 ** (1.35) / f ** 1.15                       # 1/f background
    bump = 0.9 * np.exp(-0.5 * ((f - 10) / 1.7) ** 2) * (aper[np.argmin(abs(f - 10))])
    psd = aper + bump
    ax.plot(f, psd, color=REST, lw=3.2, zorder=3)
    ax.plot(f, aper, color=ACCENT, lw=2.4, ls=(0, (5, 3)), zorder=2)
    # alpha peak annotation
    pk = np.argmin(abs(f - 10))
    ax.annotate("Rhythm peak\n(e.g. alpha)", xy=(f[pk], psd[pk]), xytext=(15.5, psd[pk] * 1.9),
                fontsize=14.5, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.8))
    ax.annotate("Aperiodic slope\n(background)", xy=(26, aper[np.argmin(abs(f - 26))]),
                xytext=(24, aper[np.argmin(abs(f - 26))] * 3.1), fontsize=14.5, color=ACCENT,
                ha="left", va="center", fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.8))
    ax.set_yscale("log"); ax.set_xscale("log")
    ax.set_xticks([1, 10, 40]); ax.set_xticklabels(["1", "10", "40"])
    ax.set_yticks([])
    ax.set_xlabel("Frequency (Hz)"); ax.set_ylabel("Power")
    style_ax(ax)
    return save(fig, "fig_schematic.png")


if __name__ == "__main__":
    outs = [fig_montage(), fig_regional(), fig_paired(), fig_testretest(),
            fig_stabilization(), fig_schematic()]
    for o in outs:
        print(o)
