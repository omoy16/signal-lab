import sys
from pathlib import Path

import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from signal_units.fix_target import find_valley_points


def make_test_df() -> pd.DataFrame:
    return pd.DataFrame(
        # fmt: off
        {
            "Date": pd.date_range("2026-04-01", periods=10, freq="D"),
            "Open": [100, 101, 99, 102, 98, 100, 97, 101, 99, 103],
            "High": [102, 103, 101, 104, 100, 102, 99, 103, 101, 105],
            "Low": [99, 97, 95, 98, 93, 96, 92, 97, 95, 100],
            "Close": [101, 99, 100, 99, 97, 98, 96, 100, 100, 104],
        }
        # fmt: on
    )


if __name__ == "__main__":
    df = make_test_df()
    indices = find_valley_points(df)

    print("=== test data ===")
    print(df.to_string(index=True))

    print("\n=== valley indices ===")
    print(indices)

    print("\n=== valley rows ===")
    if indices:
        print(df.loc[indices, ["Date", "Low"]].to_string(index=True))
    else:
        print("No match")
