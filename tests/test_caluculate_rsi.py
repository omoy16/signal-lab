import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[1] / "signal_units" / "calculate_rsi.py"
spec = importlib.util.spec_from_file_location("calculate_rsi", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)

calculate_rsi = module.calculate_rsi


def test_calculate_rsi_returns_series_with_same_length():
    close = pd.Series(
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
    )

    result = calculate_rsi(close, period=14)

    assert isinstance(result, pd.Series)
    assert len(result) == len(close)


def test_calculate_rsi_has_nan_during_warmup_period():
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])

    result = calculate_rsi(close, period=14)

    assert result.isna().all()


def test_calculate_rsi_reaches_high_value_on_strong_uptrend():
    close = pd.Series([100 + i for i in range(20)])

    result = calculate_rsi(close, period=14)

    assert result.iloc[-1] > 70


def test_calculate_rsi_reaches_low_value_on_strong_downtrend():
    close = pd.Series([120 - i for i in range(20)])

    result = calculate_rsi(close, period=14)

    assert result.iloc[-1] < 30


def test_calculate_rsi_returns_50_when_prices_do_not_move():
    close = pd.Series([100.0] * 20)

    result = calculate_rsi(close, period=14)

    assert np.isclose(result.iloc[-1], 50.0)
