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

calculate_Avg_Volume = module.calculate_Avg_Volume


def test_calculate_avg_volume_returns_series_with_same_length():
    volumes = np.array(
        [
            100,
            110,
            105,
            120,
            115,
            125,
            130,
            135,
            140,
            145,
            150,
            155,
            160,
            165,
            170,
            175,
            180,
            185,
            190,
            195,
        ]
    )

    result = calculate_Avg_Volume(volumes, period=5)

    assert isinstance(result, pd.Series)
    assert len(result) == len(volumes)


def test_calculate_avg_volume_has_nan_during_warmup_period():
    volumes = np.array([100, 110, 105, 120, 115, 125, 130, 135, 140, 145])

    result = calculate_Avg_Volume(volumes, period=5)

    # min_periods=5 なので最初の 4 行が NaN
    assert result.isna().sum() == 4
    # 5 行目（idx=4）からは NaN ではない
    assert not result.isna().iloc[4:].any()


def test_calculate_avg_volume_calculates_correct_sma():
    volumes = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])

    result = calculate_Avg_Volume(volumes, period=3)

    # 期待値: min_periods=period なので
    # idx 0, 1: NaN (warmup)
    # idx 2: (10 + 20 + 30) / 3 = 20.0
    # idx 3: (20 + 30 + 40) / 3 = 30.0
    # idx 4: (30 + 40 + 50) / 3 = 40.0
    # idx 5: (40 + 50 + 60) / 3 = 50.0

    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert np.isclose(result.iloc[2], 20.0)
    assert np.isclose(result.iloc[3], 30.0)
    assert np.isclose(result.iloc[4], 40.0)
    assert np.isclose(result.iloc[5], 50.0)


def test_calculate_avg_volume_works_with_series_input():
    volumes = pd.Series([100, 110, 105, 120, 115, 125, 130, 135, 140, 145])

    result = calculate_Avg_Volume(volumes, period=5)

    assert isinstance(result, pd.Series)
    assert len(result) == len(volumes)


def test_calculate_avg_volume_default_period_is_20():
    volumes = np.arange(1, 101)  # 1 から 100 まで

    result = calculate_Avg_Volume(volumes)  # period デフォルト

    # min_periods=20 なので最初の 19 行が NaN
    assert result.isna().sum() == 19
    # 20 行目（idx=19）からは NaN ではない
    assert not result.isna().iloc[19:].any()
