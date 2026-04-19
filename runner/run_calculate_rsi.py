import sys
from pathlib import Path

import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from signal_units.fix_target import calculate_rsi


def make_test_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2026-04-01", periods=30, freq="D"),
            # fmt: off
            "Close": [
                100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
                120, 118, 115, 111, 106, 101, 96, 92, 88, 84,
                80, 76, 73, 70, 67, 64, 61, 58, 55, 52
            ],
            # fmt: on
        }
    )


if __name__ == "__main__":
    df = make_test_df()
    df["RSI"] = calculate_rsi(df["Close"], period=14)

    print("=== price data with RSI ===")
    print(df.to_string(index=True))
