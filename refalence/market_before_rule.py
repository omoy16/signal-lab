from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import talib


# from .chart_data import ChartData
@dataclass
class ChartData:
    """チャートの基本データを保持するクラス"""

    df: pd.DataFrame
    dates: np.ndarray
    closes: np.ndarray
    opens: np.ndarray | None = None
    highs: np.ndarray | None = None
    lows: np.ndarray | None = None
    volumes: np.ndarray | None = None

    def __post_init__(self):
        self.latest_close = self.closes[-1] if len(self.closes) > 0 else None
        self.latest_date = self.dates[-1] if len(self.dates) > 0 else None


def _prepare_df(chart: ChartData) -> pd.DataFrame:
    df = chart.df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


def _safe_get(df: Optional[pd.DataFrame], idx: Optional[int], col: str):
    try:
        if df is None or idx is None:
            return None
        if idx < 0 or idx >= len(df):
            return None
        return df.at[idx, col]
    except Exception:
        return None


def _calculate_indicators(
    df: pd.DataFrame, bb_period: int = 25, rsi_period: int = 14
) -> pd.DataFrame:
    close = df["Close"].values.astype(float)
    volume = df["Volume"].values.astype(float)

    upper, middle, lower = talib.BBANDS(
        close,
        timeperiod=bb_period,
        nbdevup=2,
        nbdevdn=2,
        matype=0,
    )
    std = talib.STDDEV(close, timeperiod=bb_period)

    df["BB_Upper"] = upper
    df["BB_Lower"] = lower
    df["BB_Upper_3sigma"] = middle + (std * 3)
    df["RSI"] = talib.RSI(close, timeperiod=rsi_period)
    df["Avg_Volume"] = talib.SMA(volume, timeperiod=20)
    return df


def _detect_rsi_entries(df: pd.DataFrame) -> List[int]:
    entries: List[int] = []
    for i in range(1, len(df)):
        if pd.notna(df.at[i, "RSI"]) and pd.notna(df.at[i - 1, "RSI"]):
            if df.at[i, "RSI"] < 30 and df.at[i - 1, "RSI"] >= 30:
                entries.append(i)
    return entries


def _is_valley_with_lower_shadow(df: pd.DataFrame, i: int) -> bool:
    if i <= 0 or i >= len(df) - 1:
        return False

    row = df.iloc[i]
    prev_row = df.iloc[i - 1]
    next_row = df.iloc[i + 1]

    is_valley = (row["Low"] < prev_row["Low"]) and (row["Low"] < next_row["Low"])

    if pd.isna(row["Low"]) or row["Low"] <= 0:
        return False

    lower_shadow_size = row["Close"] - row["Low"]
    body_size = abs(row["Close"] - row["Open"])
    if body_size > 0:
        has_lower_shadow = (lower_shadow_size >= body_size * 0.8) and (
            lower_shadow_size / row["Low"] >= 0.02
        )
    else:
        has_lower_shadow = lower_shadow_size / row["Low"] >= 0.02

    if pd.notna(row["Avg_Volume"]) and row["Avg_Volume"] > 0:
        volume_spike = row["Volume"] >= row["Avg_Volume"] * 1.3
    else:
        volume_spike = False

    return bool(is_valley and has_lower_shadow and volume_spike)


def _check_band_walk_hybrid(df: pd.DataFrame, start_idx: int, end_idx: int) -> bool:
    if start_idx < 0 or end_idx >= len(df) or start_idx > end_idx:
        return False
    period = df.iloc[start_idx : end_idx + 1]
    if period.empty:
        return False

    close_ratio = (period["Close"] <= period["BB_Lower"]).mean()
    touch_ratio = (period["Low"] <= period["BB_Lower"]).mean()
    return bool(close_ratio >= 0.5 and touch_ratio >= 0.5)


def _check_slope_condition(df: pd.DataFrame, rsi_idx: int, valley_idx: int) -> bool:
    if valley_idx <= rsi_idx or valley_idx >= len(df) - 1:
        return False

    valley_low = df.at[valley_idx, "Low"]
    next_day_close = df.at[valley_idx + 1, "Close"]
    rsi_day_low = df.at[rsi_idx, "Low"]
    days_between = valley_idx - rsi_idx

    valley_slope = abs(next_day_close - valley_low)
    decline_slope = (
        abs(valley_low - rsi_day_low) / days_between if days_between > 0 else 0
    )
    return bool(valley_slope > decline_slope)


def _detect_upper_band_exit(
    row: pd.Series, proximity: float = 0.95, shadow_ratio: float = 0.02
) -> bool:
    if pd.isna(row["BB_Upper_3sigma"]) or row["BB_Upper_3sigma"] <= 0:
        return False

    threshold = row["BB_Upper_3sigma"] * proximity
    reach_3sigma = row["High"] >= threshold
    upper_shadow = row["Close"] < row["High"] * (1 - shadow_ratio)
    return bool(reach_3sigma and upper_shadow)


def _first_entry_after_rsi(df: pd.DataFrame, rsi_idx: int) -> Optional[Dict[str, int]]:
    for i in range(max(rsi_idx + 1, 1), len(df) - 1):
        if not _is_valley_with_lower_shadow(df, i):
            continue

        bb_pass = _check_band_walk_hybrid(df, rsi_idx, i)
        slope_pass = _check_slope_condition(df, rsi_idx, i)
        if bb_pass and slope_pass:
            return {
                "rsi_idx": rsi_idx,
                "entry_idx": i,
            }
    return None


def _first_exit_after_entry(df: pd.DataFrame, entry_idx: int) -> Optional[int]:
    for j in range(entry_idx + 1, len(df)):
        if _detect_upper_band_exit(df.iloc[j]):
            return j
    return None


def _attach_stage_series(result: Dict[str, Any]) -> Dict[str, Any]:
    stage_passes = pd.Series(
        {
            "1st_RSI": bool(result.get("rsi_pass", False)),
            "2nd_BB": bool(result.get("bb_pass", False)),
            "3rd_VALLEY": bool(result.get("valley_pass", False)),
            "4th_EXIT": bool(result.get("exit_pass", False)),
        },
        dtype="bool",
    )
    result["stage_passes"] = stage_passes
    result["stage_signals"] = pd.Series(
        {
            "1st_RSI": "BID" if stage_passes["1st_RSI"] else "NO",
            "2nd_BB": "BID" if stage_passes["2nd_BB"] else "NO",
            "3rd_VALLEY": "BID" if stage_passes["3rd_VALLEY"] else "NO",
            "4th_EXIT": "ASK" if stage_passes["4th_EXIT"] else "NO",
        },
        dtype="object",
    )
    return result


def analyze_market_before_stages(chart: ChartData) -> Dict[str, Any]:
    df = _prepare_df(chart)
    required = {"Open", "High", "Low", "Close", "Volume"}

    base = {
        "latest_date": chart.latest_date,
        "latest_close": chart.latest_close,
        "rsi_pass": False,
        "bb_pass": False,
        "valley_pass": False,
        "exit_pass": False,
        "rsi_idx": None,
        "latest_rsi_idx": None,
        "entry_idx": None,
        "exit_idx": None,
        "rsi_count": 0,
        "entry_count": 0,
        "exit_count": 0,
        "reason": "",
    }

    if len(df) < 30 or not required.issubset(set(df.columns)):
        base["reason"] = "Not enough data"
        return _attach_stage_series(base)

    df = _calculate_indicators(df)
    base["df"] = df

    rsi_indices = _detect_rsi_entries(df)
    base["rsi_count"] = len(rsi_indices)
    if not rsi_indices:
        base["reason"] = "No RSI entry"
        return _attach_stage_series(base)

    base["rsi_pass"] = True
    base["latest_rsi_idx"] = rsi_indices[-1]
    chosen = None
    all_entries: List[int] = []
    all_exits: List[int] = []

    for rsi_idx in rsi_indices:
        found = _first_entry_after_rsi(df, rsi_idx)
        if found is None:
            continue

        all_entries.append(found["entry_idx"])
        if chosen is None:
            chosen = found

        exit_idx = _first_exit_after_entry(df, found["entry_idx"])
        if exit_idx is not None:
            all_exits.append(exit_idx)

    base["bb_pass"] = chosen is not None
    base["valley_pass"] = chosen is not None
    base["entry_count"] = len(all_entries)
    base["exit_count"] = len(all_exits)

    if chosen is not None:
        base["rsi_idx"] = chosen["rsi_idx"]
        base["entry_idx"] = chosen["entry_idx"]
        base["exit_idx"] = _first_exit_after_entry(df, chosen["entry_idx"])
        base["exit_pass"] = base["exit_idx"] is not None
        if not base["exit_pass"]:
            base["reason"] = "No +3sigma exit"
    else:
        base["reason"] = "No BB/Valley entry"

    return _attach_stage_series(base)


def build_market_before_stage_rows(
    ticker: str, company_name: str, chart: ChartData
) -> List[Dict[str, Any]]:
    analysis = analyze_market_before_stages(chart)
    latest_date = analysis.get("latest_date", "")
    latest_close = analysis.get("latest_close", "")

    df = analysis.get("df")
    stage_signals = analysis.get("stage_signals", pd.Series(dtype="object"))

    def _date_close(idx):
        if df is None or idx is None:
            return "", ""
        d = df.at[idx, "Date"]
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        return d, df.at[idx, "Close"]

    rsi_date, rsi_close = _date_close(analysis.get("rsi_idx"))
    entry_date, entry_close = _date_close(analysis.get("entry_idx"))
    exit_date, exit_close = _date_close(analysis.get("exit_idx"))

    rows = [
        {
            "Ticker": ticker,
            "Company_Name": company_name,
            "Last_Date": latest_date,
            "Last_Price": latest_close,
            "Detect_Date": rsi_date,
            "Detect_Price": rsi_close,
            "Stage": "1st_RSI",
            "Signal": stage_signals.get("1st_RSI", "NO"),
            "extras": [
                f"RSITriggers: {analysis['rsi_count']}",
                (
                    f"RSI(at): {df.at[analysis['rsi_idx'], 'RSI']:.2f}"
                    if analysis.get("rsi_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["rsi_idx"], "RSI"])
                    else "RSI(at): N/A"
                ),
                (
                    f"PrevRSI: {df.at[analysis['rsi_idx']-1, 'RSI']:.2f}"
                    if analysis.get("rsi_idx") is not None
                    and analysis["rsi_idx"] > 0
                    and df is not None
                    and pd.notna(df.at[analysis["rsi_idx"] - 1, "RSI"])
                    else "PrevRSI: N/A"
                ),
                (
                    f"LatestRSI_Date: {df.at[analysis['latest_rsi_idx'], 'Date'].strftime('%Y-%m-%d') if hasattr(df.at[analysis['latest_rsi_idx'], 'Date'], 'strftime') else df.at[analysis['latest_rsi_idx'], 'Date']}"
                    if analysis.get("latest_rsi_idx") is not None and df is not None
                    else "LatestRSI_Date: N/A"
                ),
                analysis.get("reason", "") if not analysis["rsi_pass"] else "",
            ],
        },
        {
            "Ticker": ticker,
            "Company_Name": company_name,
            "Last_Date": latest_date,
            "Last_Price": latest_close,
            "Detect_Date": entry_date,
            "Detect_Price": entry_close,
            "Stage": "2nd_BB",
            "Signal": stage_signals.get("2nd_BB", "NO"),
            "extras": [
                "close<=-2σ & low touch >=50%",
                f"EntryCandidates: {analysis['entry_count']}",
                (
                    f"AvgVol: {df.at[analysis['entry_idx'], 'Avg_Volume']:.0f}"
                    if analysis.get("entry_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["entry_idx"], "Avg_Volume"])
                    else "AvgVol: N/A"
                ),
                analysis.get("reason", "") if not analysis["bb_pass"] else "",
            ],
        },
        {
            "Ticker": ticker,
            "Company_Name": company_name,
            "Last_Date": latest_date,
            "Last_Price": latest_close,
            "Detect_Date": entry_date,
            "Detect_Price": entry_close,
            "Stage": "3rd_VALLEY",
            "Signal": stage_signals.get("3rd_VALLEY", "NO"),
            "extras": [
                "Valley+LowerShadow+VolumeSpike",
                (
                    f"LowerShadowPct: {((df.at[analysis['entry_idx'],'Close']-df.at[analysis['entry_idx'],'Low'])/df.at[analysis['entry_idx'],'Low']*100):.2f}%"
                    if analysis.get("entry_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["entry_idx"], "Low"])
                    else "LowerShadowPct: N/A"
                ),
                (
                    f"VolRatio: {df.at[analysis['entry_idx'],'Volume']/df.at[analysis['entry_idx'],'Avg_Volume']:.2f}"
                    if analysis.get("entry_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["entry_idx"], "Avg_Volume"])
                    and df.at[analysis["entry_idx"], "Avg_Volume"] > 0
                    else "VolRatio: N/A"
                ),
                analysis.get("reason", "") if not analysis["valley_pass"] else "",
            ],
        },
        {
            "Ticker": ticker,
            "Company_Name": company_name,
            "Last_Date": latest_date,
            "Last_Price": latest_close,
            "Detect_Date": exit_date,
            "Detect_Price": exit_close,
            "Stage": "4th_EXIT",
            "Signal": stage_signals.get("4th_EXIT", "NO"),
            "extras": [
                "+3σ 95% reach and upper shadow",
                (
                    f"DistancePct: {((df.at[analysis['exit_idx'],'High']/df.at[analysis['exit_idx'],'BB_Upper_3sigma']-1)*100):.2f}%"
                    if analysis.get("exit_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["exit_idx"], "BB_Upper_3sigma"])
                    and df.at[analysis["exit_idx"], "BB_Upper_3sigma"] > 0
                    else "DistancePct: N/A"
                ),
                (
                    f"UpperShadowPct: {((df.at[analysis['exit_idx'],'High']-df.at[analysis['exit_idx'],'Close'])/df.at[analysis['exit_idx'],'High']*100):.2f}%"
                    if analysis.get("exit_idx") is not None
                    and df is not None
                    and pd.notna(df.at[analysis["exit_idx"], "High"])
                    and df.at[analysis["exit_idx"], "High"] > 0
                    else "UpperShadowPct: N/A"
                ),
                (f"Closed: {analysis['exit_count']}"),
                analysis.get("reason", "") if not analysis["exit_pass"] else "",
            ],
        },
    ]

    return rows


def check_market_before_rule(chart: ChartData) -> Dict[str, Any]:
    """
    original_rule_2026022_market_before.py の条件を
    既存Commandインターフェースで利用できる形へ変換した戦略。
    """
    analysis = analyze_market_before_stages(chart)
    stage_signals = analysis.get("stage_signals", pd.Series(dtype="object"))

    signal = "No setup"
    if not analysis["rsi_pass"]:
        signal = "No RSI entry"
    elif analysis["exit_pass"]:
        signal = stage_signals.get("4th_EXIT", "ASK")
    elif analysis["valley_pass"]:
        signal = stage_signals.get("3rd_VALLEY", "BID")
    elif analysis["bb_pass"]:
        signal = stage_signals.get("2nd_BB", "BID")
    else:
        signal = "No entry"

    df = analysis.get("df")
    latest_rsi_idx = analysis.get("latest_rsi_idx")
    if df is not None and latest_rsi_idx is not None:
        d = df.at[latest_rsi_idx, "Date"]
        latest_rsi_date_str = (
            d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        )
    else:
        latest_rsi_date_str = None

    extra = [
        f"RSITriggers: {analysis['rsi_count']}",
        f"Entries: {analysis['entry_count']}",
        f"Closed: {analysis['exit_count']}",
    ]
    if latest_rsi_date_str:
        extra.append(f"LatestRSI_Date: {latest_rsi_date_str}")
    if analysis.get("reason"):
        extra.append(analysis["reason"])

    date = analysis.get("latest_date", chart.latest_date)
    close = analysis.get("latest_close", chart.latest_close)

    return {
        "date": date,
        "close": close,
        "signal": signal,
        "extra": extra,
        "stage_passes": analysis.get("stage_passes", pd.Series(dtype="bool")),
        "stage_signals": stage_signals,
    }
