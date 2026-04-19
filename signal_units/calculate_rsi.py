import numpy as np
import pandas as pd


def calculate_rsi(
    close: np.ndarray | pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Wilder's RSI

    Parameters
    ----------
    close : close prices
    period : RSI period

    Returns
    -------
    pd.Series
    """

    close = pd.Series(close, dtype=float)

    # 前日差分
    delta = close.diff()

    # 上昇/下落を分離
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder smoothing (ワイルダーの平滑化移動平均)
    avg_gain = gain.ewm(
        alpha=1/period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/period,
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