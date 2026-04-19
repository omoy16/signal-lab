from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class ChartData:
    df: pd.DataFrame
    dates: np.ndarray
    closes: np.ndarray
    opens: np.ndarray | None = None
    highs: np.ndarray | None = None
    lows: np.ndarray | None = None
    volumes: np.ndarray | None = None


def calculate_rsi(
    closes: np.ndarray | pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    終値データから RSI を計算して返す

    手順:
      1. 前日差分を計算
      2. 上昇分と下落分に分離
      3. Wilder法で平均化
      4. RS と RSI を計算
      5. 例外ケースを補正
    """

    close = pd.Series(closes, dtype=float)

    # 前日差分
    delta = close.diff()

    # 上昇/下落を分離
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder smoothing
    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    # RS
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)

    # RSI
    rsi = 100 - (100 / (1 + relative_strength))

    # 例外ケース補正
    rsi.loc[(avg_loss == 0) & (avg_gain > 0)] = 100
    rsi.loc[(avg_loss == 0) & (avg_gain == 0)] = 50

    return rsi




def find_rsi_cross_under(
    df: pd.DataFrame,
    threshold: float = 30,
) -> List[int]:
    """
    RSIが threshold を
    上から下に抜けたインデックスを返す

    条件:
      前日 >= threshold
      当日 < threshold
    """

    today_is_under = df["RSI"] < threshold
    yesterday_was_over = df["RSI"].shift(1) >= threshold

    cross_down = today_is_under & yesterday_was_over

    return df.index[cross_down.fillna(False)].tolist()


def find_valley_points(
    df: pd.DataFrame,
) -> List[int]:
    """
    安値が前日・翌日より低い
    谷のインデックスを返す
    """

    lower_than_yesterday = df["Low"] < df["Low"].shift(1)
    lower_than_tomorrow = df["Low"] < df["Low"].shift(-1)

    valley = lower_than_yesterday & lower_than_tomorrow

    return df.index[valley.fillna(False)].tolist()


def find_lower_shadow_points(
    df: pd.DataFrame,
    shadow_body_ratio: float = 0.8,
    min_shadow_low_ratio: float = 0.02,
) -> List[int]:
    """
    下ヒゲが十分長い
    インデックスを返す

    条件:
      下ヒゲ >= 実体 * shadow_body_ratio
      下ヒゲ / Low >= min_shadow_low_ratio
    """

    lower_shadow = df["Close"] - df["Low"]
    body = (df["Close"] - df["Open"]).abs()
    shadow_low_ratio = lower_shadow / df["Low"]

    long_shadow = (lower_shadow >= body * shadow_body_ratio) & (
        shadow_low_ratio >= min_shadow_low_ratio
    )

    return df.index[long_shadow.fillna(False)].tolist()


def find_volume_spike_points(
    df: pd.DataFrame,
    volume_ratio: float = 1.3,
) -> List[int]:
    """
    出来高が平均出来高より
    volume_ratio倍以上のインデックスを返す
    """

    spike = (
        pd.notna(df["Avg_Volume"])
        & (df["Avg_Volume"] > 0)
        & (df["Volume"] >= df["Avg_Volume"] * volume_ratio)
    )

    return df.index[spike.fillna(False)].tolist()


def find_upper_band_exit_points(
    df: pd.DataFrame,
    proximity: float = 0.95,
    upper_shadow_ratio: float = 0.02,
) -> List[int]:
    """
    +3σ付近到達かつ上ヒゲを持つ
    インデックスを返す

    条件:
      High >= BB_Upper_3sigma * proximity
      Close < High * (1 - upper_shadow_ratio)
    """

    exit_signal = (
        pd.notna(df["BB_Upper_3sigma"])
        & (df["BB_Upper_3sigma"] > 0)
        & (df["High"] >= df["BB_Upper_3sigma"] * proximity)
        & (df["Close"] < df["High"] * (1 - upper_shadow_ratio))
    )

    return df.index[exit_signal.fillna(False)].tolist()


def find_band_walk_points(
    df: pd.DataFrame,
    start_idx: int,
    min_ratio: float = 0.5,
) -> List[int]:
    """
    start_idx 以降で
    BB下限沿いの推移が続いている
    インデックスを返す
    """

    if start_idx < 0 or start_idx >= len(df):
        return []

    period = df.iloc[start_idx:].copy()

    close_ratio = (period["Close"] <= period["BB_Lower"]).expanding().mean()
    low_ratio = (period["Low"] <= period["BB_Lower"]).expanding().mean()

    matched = (close_ratio >= min_ratio) & (low_ratio >= min_ratio)

    return period.index[matched.fillna(False)].tolist()


def find_rebound_stronger_than_decline_points(
    df: pd.DataFrame,
    rsi_idx: int,
) -> List[int]:
    """
    RSI起点から見て
    反発の傾きが下落の傾きを上回る
    インデックスを返す
    """

    if rsi_idx < 0 or rsi_idx >= len(df) - 1:
        return []

    target = df.iloc[rsi_idx + 1 : -1].copy()
    if target.empty:
        return []

    valley_low = target["Low"]
    next_close = df["Close"].shift(-1).loc[target.index]
    rsi_low = df.at[rsi_idx, "Low"]
    days = target.index - rsi_idx

    rebound = (next_close - valley_low).abs()
    decline = (valley_low - rsi_low).abs() / days

    stronger = rebound > decline

    return target.index[stronger.fillna(False)].tolist()
