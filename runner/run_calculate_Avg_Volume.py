import sys
from pathlib import Path

import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from signal_units.fix_target import calculate_Avg_Volume


def make_test_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2026-04-01", periods=30, freq="D"),
            # fmt: off
            "Volume": [
                1000, 1100, 1050, 1200, 1150, 1250, 1300, 1350, 1400, 1450,
                1500, 1480, 1450, 1420, 1400, 1380, 1360, 1340, 1320, 1300,
                1280, 1260, 1240, 1220, 1200, 1180, 1160, 1140, 1120, 1100
            ],
            # fmt: on
        }
    )


if __name__ == "__main__":
    df = make_test_df()
    df["Avg_Volume"] = calculate_Avg_Volume(df["Volume"], period=5)

    print("=== Volume data with 5-day Average ===")
    print(df.to_string(index=True))

    print("\n=== デフォルト period=20 での計算例 ===")
    df_20 = make_test_df()
    df_20["Avg_Volume_20"] = calculate_Avg_Volume(df_20["Volume"])
    print(df_20[["Date", "Volume", "Avg_Volume_20"]].to_string(index=True))
