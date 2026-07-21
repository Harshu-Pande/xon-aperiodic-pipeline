"""Cohort statistics chosen for THIS study's questions:

1. Can the headset recover the exponent accurately?  -> measurement quality / yield
   (fit r^2, exponent range, clean-minute retention, rejection rates).
2. Is it reliable across a person's repeat sessions?  -> test-retest reliability (ICC),
   plus Pearson r and the mean absolute session-to-session difference.
3. Does it hold up in a noisy room (movie) vs quiet (rest)?  -> paired condition contrast.
4. Where on the scalp, and how few minutes are needed?  -> regional summary + convergence.

Only "relevant" analyses - the ones a reviewer of this study would ask for. Everything
degrades gracefully on small / incomplete cohorts (returns a note instead of crashing).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from scipy import stats as _sps
except Exception:                       # pragma: no cover
    _sps = None


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _ok(df: pd.DataFrame) -> pd.DataFrame:
    """Only successfully-processed rows with a real AVERAGE exponent."""
    if df.empty:
        return df
    d = df.copy()
    if "status" in d.columns:
        d = d[d["status"].astype(str) != "error"]
    d["AVERAGE_exponent"] = _num(d.get("AVERAGE_exponent"))
    return d[d["AVERAGE_exponent"].notna()]


def _describe(values: np.ndarray) -> Dict[str, Any]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return dict(n=0, mean="", sd="", median="", iqr="", min="", max="")
    q1, q3 = np.percentile(values, [25, 75])
    return dict(n=int(len(values)), mean=round(float(np.mean(values)), 4),
                sd=round(float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, 4),
                median=round(float(np.median(values)), 4), iqr=round(float(q3 - q1), 4),
                min=round(float(np.min(values)), 4), max=round(float(np.max(values)), 4))


# --------------------------------------------------------------------------
# 1. measurement quality / yield
# --------------------------------------------------------------------------
def quality_summary(master: pd.DataFrame) -> pd.DataFrame:
    d = _ok(master)
    if d.empty:
        return pd.DataFrame()
    metrics = {
        "AVERAGE_exponent": "aperiodic exponent",
        "AVERAGE_r_squared": "fit r^2",
        "pct_epochs_kept": "% epochs kept",
        "clean_minutes": "clean minutes",
        "AVERAGE_exponent_sd": "across-channel SD",
    }
    rows = []
    groups = [("all", d)]
    if "condition" in d.columns:
        groups += [(str(c), g) for c, g in d.groupby("condition")]
    for gname, g in groups:
        for col, label in metrics.items():
            if col not in g.columns:
                continue
            desc = _describe(_num(g[col]).values)
            rows.append(dict(group=gname, metric=label, **desc))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 2. test-retest reliability (ICC)
# --------------------------------------------------------------------------
def _icc_2_1(matrix: np.ndarray) -> Optional[float]:
    """ICC(2,1): two-way random effects, single measurement, absolute agreement.
    matrix = subjects x raters(sessions), complete (no NaN)."""
    n, k = matrix.shape
    if n < 2 or k < 2:
        return None
    grand = matrix.mean()
    row_means = matrix.mean(axis=1)
    col_means = matrix.mean(axis=0)
    ss_total = ((matrix - grand) ** 2).sum()
    ss_row = k * ((row_means - grand) ** 2).sum()
    ss_col = n * ((col_means - grand) ** 2).sum()
    ss_err = ss_total - ss_row - ss_col
    df_row, df_col, df_err = n - 1, k - 1, (n - 1) * (k - 1)
    if df_err <= 0:
        return None
    msr, msc, mse = ss_row / df_row, ss_col / df_col, ss_err / df_err
    denom = msr + (k - 1) * mse + (k / n) * (msc - mse)
    if denom == 0:
        return None
    return float((msr - mse) / denom)


def reliability(master: pd.DataFrame) -> pd.DataFrame:
    """Test-retest across a participant's repeat sessions, per condition."""
    d = _ok(master)
    needed = {"participant", "session", "condition"}
    if d.empty or not needed.issubset(d.columns):
        return pd.DataFrame()
    d = d[d["participant"].astype(str).str.len() > 0]
    d = d[d["session"].astype(str).str.len() > 0]
    rows = []
    for cond, g in d.groupby("condition"):
        # subjects x sessions matrix of AVERAGE exponent
        pivot = g.pivot_table(index="participant", columns="session",
                              values="AVERAGE_exponent", aggfunc="mean")
        pivot = pivot.dropna(axis=0, how="any")          # listwise: complete sessions only
        n_sub, k_ses = pivot.shape
        row = dict(condition=str(cond), n_participants_complete=int(n_sub),
                   n_sessions=int(k_ses))
        if n_sub >= 2 and k_ses >= 2:
            mat = pivot.values.astype(float)
            icc = _icc_2_1(mat)
            row["ICC(2,1)"] = round(icc, 4) if icc is not None else ""
            lo, hi = _icc_ci(mat)
            row["ICC_95CI_low"], row["ICC_95CI_high"] = lo, hi
            # Pearson r + mean abs diff on the first two sessions
            s = sorted(pivot.columns)[:2]
            a, b = pivot[s[0]].values, pivot[s[1]].values
            if _sps is not None and len(a) >= 3 and np.std(a) > 0 and np.std(b) > 0:
                r, p = _sps.pearsonr(a, b)
                row["pearson_r"] = round(float(r), 4)
                row["pearson_p"] = round(float(p), 4)
            row["mean_abs_session_diff"] = round(float(np.mean(np.abs(a - b))), 4)
            row["note"] = _icc_label(icc)
        else:
            row["ICC(2,1)"] = ""
            row["note"] = "need >=2 participants with >=2 complete sessions"
        rows.append(row)
    return pd.DataFrame(rows)


def _icc_ci(mat: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Bootstrap 95% CI for ICC by resampling subjects with replacement."""
    rng = np.random.default_rng(seed)
    n = mat.shape[0]
    if n < 3:
        return ("", "")
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        v = _icc_2_1(mat[idx])
        if v is not None and np.isfinite(v):
            vals.append(v)
    if len(vals) < 20:
        return ("", "")
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (round(float(lo), 3), round(float(hi), 3))


def _icc_label(icc: Optional[float]) -> str:
    if icc is None:
        return ""
    if icc < 0.5:
        return "poor reliability"
    if icc < 0.75:
        return "moderate reliability"
    if icc < 0.9:
        return "good reliability"
    return "excellent reliability"


# --------------------------------------------------------------------------
# 3. rest vs movie (quiet vs noisy) paired contrast
# --------------------------------------------------------------------------
def condition_contrast(master: pd.DataFrame, quiet: str = "rest", noisy: str = "movie") -> Dict[str, Any]:
    d = _ok(master)
    if d.empty or not {"participant", "session", "condition"}.issubset(d.columns):
        return dict(note="metadata (participant/session/condition) unavailable")
    d["key"] = d["participant"].astype(str) + "|" + d["session"].astype(str)
    q = d[d["condition"] == quiet].set_index("key")["AVERAGE_exponent"]
    n = d[d["condition"] == noisy].set_index("key")["AVERAGE_exponent"]
    common = sorted(set(q.index) & set(n.index))
    if len(common) < 2:
        return dict(quiet=quiet, noisy=noisy, n_pairs=len(common),
                    note="need >=2 participant-sessions with BOTH conditions")
    qa, na = q.loc[common].values.astype(float), n.loc[common].values.astype(float)
    diff = na - qa
    out = dict(quiet=quiet, noisy=noisy, n_pairs=len(common),
               quiet_mean=round(float(np.mean(qa)), 4), noisy_mean=round(float(np.mean(na)), 4),
               mean_diff_noisy_minus_quiet=round(float(np.mean(diff)), 4))
    sd = np.std(diff, ddof=1) if len(diff) > 1 else 0.0
    out["cohen_dz"] = round(float(np.mean(diff) / sd), 4) if sd > 0 else ""
    if _sps is not None and len(diff) > 1:
        sem = sd / np.sqrt(len(diff))
        tcrit = float(_sps.t.ppf(0.975, len(diff) - 1))
        out["diff_95ci_low"] = round(float(np.mean(diff) - tcrit * sem), 4)
        out["diff_95ci_high"] = round(float(np.mean(diff) + tcrit * sem), 4)
    if _sps is not None and len(common) >= 3:
        try:
            t, p = _sps.ttest_rel(na, qa)
            out["paired_t"] = round(float(t), 4)
            out["paired_t_p"] = round(float(p), 4)
        except Exception:
            pass
        try:
            w, pw = _sps.wilcoxon(na, qa)
            out["wilcoxon_p"] = round(float(pw), 4)
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------
# 4. regional summary (frontal / central / parietal)
# --------------------------------------------------------------------------
def regional_summary(master: pd.DataFrame, regions: Dict[str, List[str]]) -> pd.DataFrame:
    d = _ok(master)
    if d.empty:
        return pd.DataFrame()
    rows = []
    per_recording_region: Dict[str, List[float]] = {r: [] for r in regions}
    for _, rec in d.iterrows():
        for region, chans in regions.items():
            vals = [_safe_float(rec.get(f"{ch}_exponent")) for ch in chans]
            vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
            # ignore interpolated channels in the regional mean
            vals2 = []
            for ch in chans:
                v = _safe_float(rec.get(f"{ch}_exponent"))
                if v is None:
                    continue
                if bool(rec.get(f"{ch}_interpolated")) or bool(rec.get(f"{ch}_excluded")):
                    continue
                vals2.append(v)
            use = vals2 if vals2 else vals
            if use:
                per_recording_region[region].append(float(np.mean(use)))
    for region, vals in per_recording_region.items():
        rows.append(dict(region=region, **_describe(np.array(vals))))
    df = pd.DataFrame(rows)
    return df


def _regional_by_participant(master: pd.DataFrame, regions: Dict[str, List[str]],
                             condition: Optional[str] = "rest") -> pd.DataFrame:
    """One row per PARTICIPANT (mean region exponent across their recordings), so the
    regional test uses independent subjects instead of pseudoreplicating recordings.

    ``condition`` restricts which recordings feed the average (default 'rest' only; the two
    rest sessions per participant are then averaged). Set to None to use all recordings."""
    d = _ok(master)
    if d.empty or "participant" not in d.columns:
        return pd.DataFrame()
    if condition is not None and "condition" in d.columns:
        d = d[d["condition"] == condition]
        if d.empty:
            return pd.DataFrame()
    rows = []
    for _, rec in d.iterrows():
        row = {"participant": rec.get("participant", "")}
        for region, chans in regions.items():
            vals = []
            for ch in chans:
                v = _safe_float(rec.get(f"{ch}_exponent"))
                if v is None or bool(rec.get(f"{ch}_interpolated")) or bool(rec.get(f"{ch}_excluded")):
                    continue
                vals.append(v)
            row[region] = np.mean(vals) if vals else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    return df.groupby("participant")[list(regions.keys())].mean().dropna()


def _holm(pvals: List[float]) -> List[float]:
    order = np.argsort(pvals); k = len(pvals); out = [None] * k
    for rank, idx in enumerate(order):
        out[idx] = min(1.0, float(pvals[idx]) * (k - rank))
    # enforce monotonicity
    for i in range(1, k):
        prev = out[order[i - 1]]
        if out[order[i]] < prev:
            out[order[i]] = prev
    return out


def regional_test(master: pd.DataFrame, regions: Dict[str, List[str]],
                  condition: Optional[str] = "rest") -> Dict[str, Any]:
    """Friedman omnibus + Holm-corrected pairwise Wilcoxon signed-rank across scalp regions,
    at the PARTICIPANT level (independent subjects — no pseudoreplication). Uses ``condition``
    recordings only (default 'rest', averaged across sessions)."""
    if _sps is None:
        return dict(note="scipy unavailable")
    pp = _regional_by_participant(master, regions, condition=condition)
    names = list(regions.keys())
    if len(pp) < 3 or len(names) < 3:
        return dict(note=f"need >=3 participants with all regions (have {len(pp)})")
    try:
        stat, p = _sps.friedmanchisquare(*[pp[r].values for r in names])
    except Exception as exc:
        return dict(note=f"Friedman failed: {exc}")
    out = dict(test="Friedman (participant-level)", condition=(condition or "all"),
               regions=names, n_participants=int(len(pp)),
               statistic=round(float(stat), 4), p_value=round(float(p), 4),
               region_means={r: round(float(pp[r].mean()), 4) for r in names})
    # post-hoc pairwise (only if omnibus is at least suggestive)
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]
    raw = []
    for a, b in pairs:
        try:
            w = _sps.wilcoxon(pp[a].values, pp[b].values)
            raw.append((a, b, float(w.pvalue), round(float((pp[a] - pp[b]).mean()), 4)))
        except Exception:
            raw.append((a, b, float("nan"), float("nan")))
    holm = _holm([r[2] for r in raw])
    out["posthoc"] = [dict(pair=f"{a} vs {b}", mean_diff=d, p_raw=round(p, 4),
                           p_holm=round(hp, 4), significant=(hp < 0.05))
                      for (a, b, p, d), hp in zip(raw, holm)]
    return out


# --------------------------------------------------------------------------
# 5. reliability vs recording length ("how few minutes are enough")
# --------------------------------------------------------------------------
def _spearman_brown(r: float) -> float:
    """Correct a half-length (odd vs even) correlation up to full-length reliability."""
    if r <= -1:
        return -1.0
    return float(2.0 * r / (1.0 + r))


def reliability_by_duration(results: List[Any], split_half_target: float = 0.90,
                            icc_target: float = 0.75, grid_step_min: float = 0.5,
                            min_recordings: int = 4, min_n: int = 8) -> Dict[str, Any]:
    """How reliable the exponent estimate is as a function of how much clean data is used.

    Two grounded curves, both as a function of duration L:
      * split-half (odd vs even epochs) internal consistency, Spearman-Brown corrected
        (target >= 0.90; Leyva-style epoch-increment reliability), and
      * between-session test-retest ICC(2,1) (target >= 0.75 = 'good'; McKeown 2024),
    plus the shortest L at which each target is met. This is the rigorous answer to
    'how few minutes of a noisy recording match a long one?'.
    """
    # gather per-recording duration curves with metadata
    curves = []
    for r in results:
        d = getattr(r, "duration_df", None)
        if d is None or d.empty:
            continue
        meta = getattr(r, "metadata", None)
        curves.append(dict(
            participant=getattr(meta, "participant", ""), session=getattr(meta, "session", ""),
            condition=getattr(meta, "condition", ""), df=d.sort_values("clean_minutes")))
    if len(curves) < min_recordings:
        return dict(note=f"need >= {min_recordings} recordings with a duration curve "
                         f"(have {len(curves)})", curve=pd.DataFrame())

    max_minutes = max(float(c["df"]["clean_minutes"].max()) for c in curves)
    grid = np.arange(grid_step_min, max_minutes + 1e-6, grid_step_min)

    def _at(df: pd.DataFrame, col: str, L: float) -> Optional[float]:
        x = df["clean_minutes"].values
        if L > x.max() + 1e-6 or L < x.min() - 1e-6:
            return None
        y = pd.to_numeric(df[col], errors="coerce").values
        ok = np.isfinite(y)
        if ok.sum() < 2:
            return None
        return float(np.interp(L, x[ok], y[ok]))

    rows = []
    for L in grid:
        odd, even, all_by_key = [], [], {}
        errs = []
        for c in curves:
            df = c["df"]
            eo, ee = _at(df, "exponent_odd", L), _at(df, "exponent_even", L)
            ea = _at(df, "exponent_all", L)
            if eo is not None and ee is not None:
                odd.append(eo); even.append(ee)
            if ea is not None:
                # subject for test-retest = participant+condition; raters = session
                key = (str(c["participant"]), str(c["condition"]))
                all_by_key.setdefault(key, {})[str(c["session"])] = ea
                full = _at(df, "exponent_all", float(df["clean_minutes"].max()))
                if full is not None:
                    errs.append(abs(ea - full))
        n_split = len(odd)
        sh = ""
        if n_split >= min_recordings and np.std(odd) > 0 and np.std(even) > 0 and _sps is not None:
            r_half = float(_sps.pearsonr(odd, even)[0])
            sh = round(_spearman_brown(r_half), 4)
        # ICC across session pairs
        mat = [list(v.values()) for v in all_by_key.values() if len(v) >= 2]
        # keep only balanced 2-session rows
        two = [m[:2] for m in mat if len(m) >= 2]
        icc = ""
        n_icc = len(two)
        if n_icc >= min_recordings:
            iccv = _icc_2_1(np.array(two, dtype=float))
            icc = round(iccv, 4) if iccv is not None else ""
        rows.append(dict(minutes=round(float(L), 3),
                         split_half_reliability=sh, n_split_half=n_split,
                         test_retest_icc=icc, n_icc=n_icc,
                         mean_abs_error_to_full=round(float(np.mean(errs)), 4) if errs else ""))

    curve = pd.DataFrame(rows)

    # Only trust a duration where at least ``min_n`` recordings contribute. Beyond that,
    # the sample collapses (few recordings are long enough, and test-retest needs a matched
    # pair of sessions), so the estimate becomes noise and must not drive conclusions.
    def _trust(col: str, ncol: str) -> pd.DataFrame:
        return curve[pd.to_numeric(curve[ncol], errors="coerce") >= min_n]

    def _first_at_least(col: str, ncol: str, target: float) -> str:
        sub = _trust(col, ncol)
        sub = sub[pd.to_numeric(sub[col], errors="coerce") >= target]
        return float(sub["minutes"].iloc[0]) if len(sub) else ""

    def _max(col: str, ncol: str) -> Any:
        sub = pd.to_numeric(_trust(col, ncol)[col], errors="coerce").dropna()
        return round(float(sub.max()), 4) if len(sub) else ""

    def _max_trustworthy_minutes() -> Any:
        sub = curve[(pd.to_numeric(curve["n_icc"], errors="coerce") >= min_n) |
                    (pd.to_numeric(curve["n_split_half"], errors="coerce") >= min_n)]
        return float(sub["minutes"].max()) if len(sub) else ""

    return dict(
        curve=curve,
        split_half_target=split_half_target, icc_target=icc_target, min_n=min_n,
        minutes_for_split_half=_first_at_least("split_half_reliability", "n_split_half", split_half_target),
        minutes_for_good_icc=_first_at_least("test_retest_icc", "n_icc", icc_target),
        max_split_half=_max("split_half_reliability", "n_split_half"),
        max_icc=_max("test_retest_icc", "n_icc"),
        max_trustworthy_minutes=_max_trustworthy_minutes(),
        n_recordings=len(curves),
    )


def stabilization_summary(master: pd.DataFrame) -> Dict[str, Any]:
    """Cohort view of the per-recording 'minutes for this person's estimate to stabilize'
    (odd/even halves agree)."""
    d = _ok(master)
    if d.empty or "minutes_to_stabilize" not in d.columns:
        return dict(note="per-recording stabilization not computed")
    vals = _num(d["minutes_to_stabilize"]).dropna().values
    n_tot = int(len(d))
    out = dict(n_recordings=n_tot, n_stabilized=int(len(vals)),
               pct_stabilized=round(100.0 * len(vals) / n_tot, 1) if n_tot else 0.0)
    if len(vals):
        desc = _describe(vals)
        out.update({f"precise_minutes_{k}": v for k, v in desc.items() if k in ("median", "iqr", "min", "max")})
    if "minutes_to_converge" in d.columns:
        cvals = _num(d["minutes_to_converge"]).dropna().values
        if len(cvals):
            cdesc = _describe(cvals)
            out.update({f"reach_full_value_minutes_{k}": v for k, v in cdesc.items()
                        if k in ("median", "iqr", "min", "max")})
    return out


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


# --------------------------------------------------------------------------
# assemble a text summary
# --------------------------------------------------------------------------
def _duration_matrix(results: List[Any], step_min: float = 1.0):
    """Interpolate every recording's exponent-vs-clean-minutes curve onto a common minute
    grid (1, 2, 3, … min). Returns (grid, rows) where each row has participant/condition/
    session and a values array aligned to the grid (NaN past that recording's length)."""
    curves = []
    max_min = 0.0
    for r in results:
        d = getattr(r, "duration_df", None)
        meta = getattr(r, "metadata", None)
        if d is None or getattr(d, "empty", True) or "exponent_all" not in d.columns:
            continue
        d = d.dropna(subset=["exponent_all"]).sort_values("clean_minutes")
        if len(d) < 2:
            continue
        x = d["clean_minutes"].values.astype(float)
        y = pd.to_numeric(d["exponent_all"], errors="coerce").values.astype(float)
        curves.append((meta, x, y))
        max_min = max(max_min, float(x.max()))
    if not curves or max_min < step_min:
        return None
    grid = np.arange(step_min, max_min + 1e-9, step_min)
    rows = []
    for meta, x, y in curves:
        vals = np.full(len(grid), np.nan)
        ok = np.isfinite(y)
        for i, L in enumerate(grid):
            if x.min() - 1e-9 <= L <= x.max() + 1e-9 and ok.sum() >= 2:
                vals[i] = float(np.interp(L, x[ok], y[ok]))
        rows.append(dict(participant=getattr(meta, "participant", ""),
                         condition=getattr(meta, "condition", ""),
                         session=getattr(meta, "session", ""), values=vals))
    return grid, rows


def adjacent_duration_icc(results: List[Any], step_min: float = 1.0, icc_target: float = 0.75,
                          min_n: int = 8) -> Dict[str, Any]:
    """How much the per-recording exponent changes as clean data accumulates, expressed as
    the ICC(2,1) between adjacent cumulative durations (1 vs 2 min, 2 vs 3 min, …) across
    recordings. As the estimate stops changing, this ICC approaches 1; the length at which
    it first reaches ``icc_target`` and stays is when the estimate has stabilised."""
    dm = _duration_matrix(results, step_min)
    if dm is None:
        return dict(note="no duration curves available", curve=pd.DataFrame())
    grid, rows = dm
    M = np.array([r["values"] for r in rows])          # recordings x grid
    out_rows = []
    for i in range(len(grid) - 1):
        a, b = M[:, i], M[:, i + 1]
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() >= min_n:
            icc = _icc_2_1(np.column_stack([a[mask], b[mask]]))
            out_rows.append(dict(minutes=round(float(grid[i + 1]), 2),
                                 icc=round(icc, 4) if icc is not None else np.nan,
                                 n=int(mask.sum())))
    curve = pd.DataFrame(out_rows)
    minutes_to_stable = ""
    if not curve.empty:
        vals = pd.to_numeric(curve["icc"], errors="coerce").values
        mins = curve["minutes"].values
        for i in range(len(vals)):
            if np.all(vals[i:] >= icc_target):
                minutes_to_stable = float(mins[i])
                break
    return dict(curve=curve, icc_target=icc_target, minutes_to_stable_icc=minutes_to_stable,
                step_min=step_min)


def group_exponent_by_duration(results: List[Any], step_min: float = 1.0) -> Dict[str, Any]:
    """Group-mean aperiodic exponent (± SEM) at each cumulative duration, overall and split
    by condition (rest/movie). Shows how the group exponent changes with recording length and
    where it approaches an asymptote."""
    dm = _duration_matrix(results, step_min)
    if dm is None:
        return dict(note="no duration curves available")
    grid, rows = dm

    def _summ(sel):
        M = np.array([r["values"] for r in sel]) if sel else np.empty((0, len(grid)))
        out = []
        for i, L in enumerate(grid):
            col = M[:, i] if M.size else np.array([])
            col = col[np.isfinite(col)]
            if len(col) >= 1:
                out.append(dict(minutes=round(float(L), 2), mean=round(float(col.mean()), 4),
                                sem=round(float(col.std(ddof=1) / np.sqrt(len(col))), 4) if len(col) > 1 else 0.0,
                                n=int(len(col))))
        return pd.DataFrame(out)

    conds = sorted({r["condition"] for r in rows if r["condition"]})
    return dict(overall=_summ(rows),
                by_condition={c: _summ([r for r in rows if r["condition"] == c]) for c in conds})


def demographics_analysis(master: pd.DataFrame, demo_csv, condition: Optional[str] = "rest"
                          ) -> Dict[str, Any]:
    """Merge a demographics CSV (participant, age, sex) with each participant's mean exponent
    (from ``condition`` recordings) and test exponent~age (Pearson) and exponent~sex (group
    comparison). Returns a table + stats, or a note if no/invalid CSV."""
    if not demo_csv:
        return dict(note="no demographics CSV provided")
    try:
        demo = pd.read_csv(demo_csv, dtype=str)
    except Exception as exc:
        return dict(note=f"could not read demographics CSV ({exc})")
    demo.columns = [c.strip().lower() for c in demo.columns]
    if "participant" not in demo.columns:
        return dict(note="demographics CSV needs a 'participant' column")
    d = _ok(master)
    if condition and "condition" in d.columns:
        d = d[d["condition"] == condition]
    if d.empty:
        return dict(note="no recordings to attach demographics to")
    pexp = d.groupby("participant")["AVERAGE_exponent"].mean().reset_index()
    merged = pexp.merge(demo, on="participant", how="inner")
    if merged.empty:
        return dict(note="demographics did not match any participant id")
    out = dict(n=int(len(merged)), table=merged)
    if "age" in merged.columns:
        merged["age"] = _num(merged["age"])
        a = merged.dropna(subset=["age", "AVERAGE_exponent"])
        if _sps is not None and len(a) >= 3 and a["age"].std() > 0:
            r, p = _sps.pearsonr(a["age"].values, a["AVERAGE_exponent"].values)
            out["age_pearson_r"] = round(float(r), 4)
            out["age_pearson_p"] = round(float(p), 4)
            out["age_n"] = int(len(a))
    if "sex" in merged.columns:
        groups = {str(s): g["AVERAGE_exponent"].astype(float).values
                  for s, g in merged.groupby("sex") if str(s).strip()}
        out["sex_means"] = {k: round(float(np.mean(v)), 4) for k, v in groups.items()}
        if _sps is not None and len(groups) == 2:
            vals = list(groups.values())
            if all(len(v) >= 2 for v in vals):
                try:
                    u, p = _sps.mannwhitneyu(vals[0], vals[1], alternative="two-sided")
                    out["sex_mannwhitney_p"] = round(float(p), 4)
                except Exception:
                    pass
    return out


def compute_all(master: pd.DataFrame, results: List[Any], regions: Dict[str, List[str]],
                quiet: str, noisy: str, split_half_target: float = 0.90,
                icc_target: float = 0.75, min_n: int = 8,
                min_clean_minutes: float = 0.0, region_condition: str = "rest",
                demographics_csv=None) -> Dict[str, Any]:
    n_before = len(master)
    excluded = []
    if min_clean_minutes and min_clean_minutes > 0 and "clean_minutes" in master.columns:
        cm = _num(master["clean_minutes"])
        excluded = list(master.loc[cm < float(min_clean_minutes), "subject_id"]) if "subject_id" in master.columns else []
        master = master[cm >= float(min_clean_minutes)]
    return dict(
        inclusion=dict(min_clean_minutes=min_clean_minutes, n_before=n_before,
                       n_included=len(master), n_excluded=n_before - len(master),
                       excluded_recordings="; ".join(map(str, excluded))),
        quality=quality_summary(master),
        reliability=reliability(master),                       # full-length test-retest ICC
        contrast=condition_contrast(master, quiet, noisy),
        regional=regional_summary(master, regions),
        regional_test=regional_test(master, regions, condition=region_condition),
        regional_pp=_regional_by_participant(master, regions, condition=region_condition),
        region_condition=region_condition,
        duration_reliability=reliability_by_duration(results, split_half_target, icc_target, min_n=min_n),
        adjacent_icc=adjacent_duration_icc(results, step_min=1.0, icc_target=icc_target, min_n=min_n),
        group_exponent_duration=group_exponent_by_duration(results, step_min=1.0),
        stabilization=stabilization_summary(master),
        demographics=demographics_analysis(master, demographics_csv, condition=region_condition),
    )
