import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[1] / "signal_units" / "fix_target.py"
spec = importlib.util.spec_from_file_location("fix_target", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)

calculate_BB_Upper_3sigma = module.calculate_BB_Upper_3sigma


def test_calculate_bb_upper_3sigma_returns_series_with_same_length():
    closes = np.array([100.0 + i for i in range(30)])

    result = calculate_BB_Upper_3sigma(closes, period=20)

    assert isinstance(result, pd.Series)
    assert len(result) == len(closes)


def test_calculate_bb_upper_3sigma_has_nan_during_warmup_period():
    closes = np.array([100.0 + i for i in range(30)])

    result = calculate_BB_Upper_3sigma(closes, period=20)

    # min_periods=20 なので最初の 19 行が NaN
    assert result.isna().sum() == 19
    assert not result.isna().iloc[19:].any()


def test_calculate_bb_upper_3sigma_is_above_middle():
    closes = np.array([100.0 + i * 0.5 for i in range(30)])

    result = calculate_BB_Upper_3sigma(closes, period=20)

    close = pd.Series(closes, dtype=float)
    middle = close.rolling(window=20, min_periods=20).mean()

    valid = result.dropna()
    assert (valid > middle.dropna()).all()


def test_calculate_bb_upper_3sigma_calculates_correct_value():
    closes = pd.Series([100.0] * 20 + [110.0])

    result = calculate_BB_Upper_3sigma(closes, period=20)

    close = pd.Series(closes, dtype=float)
    middle = close.rolling(window=20, min_periods=20).mean()
    std = close.rolling(window=20, min_periods=20).std(ddof=1)
    expected = middle + std * 3

    assert np.isclose(result.iloc[19], expected.iloc[19])
    assert np.isclose(result.iloc[20], expected.iloc[20])


def test_calculate_bb_upper_3sigma_works_with_series_input():
    closes = pd.Series([100.0 + i for i in range(30)])

    result = calculate_BB_Upper_3sigma(closes, period=20)

    assert isinstance(result, pd.Series)
    assert len(result) == len(closes)


def test_calculate_bb_upper_3sigma_default_period_is_20():
    closes = np.array([100.0 + i for i in range(40)])

    result = calculate_BB_Upper_3sigma(closes)  # period デフォルト

    assert result.isna().sum() == 19
    assert not result.isna().iloc[19:].any()
