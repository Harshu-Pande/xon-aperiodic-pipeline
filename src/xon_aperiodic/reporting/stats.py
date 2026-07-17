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


def regional_test(master: pd.DataFrame, regions: Dict[str, List[str]]) -> Dict[str, Any]:
    """Friedman test across regions on recordings that have all regions (non-parametric,
    repeated measures)."""
    d = _ok(master)
    if d.empty or _sps is None:
        return dict(note="unavailable")
    region_names = list(regions.keys())
    per_region_cols = []
    matrix = []
    for _, rec in d.iterrows():
        region_vals = []
        for region in region_names:
            vals = []
            for ch in regions[region]:
                v = _safe_float(rec.get(f"{ch}_exponent"))
                if v is None or bool(rec.get(f"{ch}_interpolated")) or bool(rec.get(f"{ch}_excluded")):
                    continue
                vals.append(v)
            region_vals.append(np.mean(vals) if vals else np.nan)
        if all(np.isfinite(region_vals)):
            matrix.append(region_vals)
    if len(matrix) < 3 or len(region_names) < 3:
        return dict(note=f"need >=3 recordings with all {len(region_names)} regions "
                         f"(have {len(matrix)})")
    arr = np.array(matrix)
    try:
        stat, p = _sps.friedmanchisquare(*[arr[:, i] for i in range(arr.shape[1])])
        return dict(test="Friedman", regions=region_names, n_recordings=len(matrix),
                    statistic=round(float(stat), 4), p_value=round(float(p), 4))
    except Exception as exc:
        return dict(note=f"Friedman failed: {exc}")


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
                            min_recordings: int = 4) -> Dict[str, Any]:
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

    def _first_at_least(col: str, target: float) -> str:
        sub = curve[pd.to_numeric(curve[col], errors="coerce") >= target]
        return float(sub["minutes"].iloc[0]) if len(sub) else ""

    return dict(
        curve=curve,
        split_half_target=split_half_target, icc_target=icc_target,
        minutes_for_split_half=_first_at_least("split_half_reliability", split_half_target),
        minutes_for_good_icc=_first_at_least("test_retest_icc", icc_target),
        max_split_half=float(pd.to_numeric(curve["split_half_reliability"], errors="coerce").max())
            if curve["split_half_reliability"].astype(str).str.len().gt(0).any() else "",
        max_icc=float(pd.to_numeric(curve["test_retest_icc"], errors="coerce").max())
            if curve["test_retest_icc"].astype(str).str.len().gt(0).any() else "",
        n_recordings=len(curves),
    )


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
def compute_all(master: pd.DataFrame, results: List[Any], regions: Dict[str, List[str]],
                quiet: str, noisy: str, split_half_target: float = 0.90,
                icc_target: float = 0.75) -> Dict[str, Any]:
    return dict(
        quality=quality_summary(master),
        reliability=reliability(master),                       # full-length test-retest ICC
        contrast=condition_contrast(master, quiet, noisy),
        regional=regional_summary(master, regions),
        regional_test=regional_test(master, regions),
        duration_reliability=reliability_by_duration(results, split_half_target, icc_target),
    )
