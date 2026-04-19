# オリジナルストラテジー第1号（market_before_rule）解説

このドキュメントでは、`src/strategies/market_before_rule.py` の挙動と、コミット `d4a9cc6` で追加・変更されたファイルについて解説します。

---

## 1. 概要：このストラテジーが検出するパターン

このストラテジーは、**「売られすぎからのリバウンド狙い」**のパターンを4つのステージに分けて検出します。

| ステージ | キー名 | 内容 |
|---|---|---|
| 1st_RSI | `rsi_pass` | RSIが30を下抜けた「売られすぎ」起点を検出 |
| 2nd_BB | `bb_pass` | ボリンジャーバンド -2σ沿いの下落継続を確認 |
| 3rd_VALLEY | `valley_pass` | 出来高急増を伴う下ヒゲ谷（反転シグナル）を検出 |
| 4th_EXIT | `exit_pass` | +3σ付近への到達＋上ヒゲで利確タイミングを検出 |

全ステージが成立すれば **BID（買い）→ ASK（売り）** の完全なトレードシグナルが生成されます。

---

## 2. 追加・変更されたファイル

### A. `src/strategies/market_before_rule.py`（新規追加）

ストラテジーの本体です。以下の関数から構成されています。

#### 補助関数

- **`_prepare_df(chart)`**
  日付列のソートと、OHLCV各列の数値型変換を行うデータ前処理関数です。

- **`_safe_get(df, idx, col)`**
  インデックス範囲外や `None` に対して安全に値を取得するユーティリティです。

- **`_calculate_indicators(df)`**
  テクニカル指標を一括計算します。
  - **ボリンジャーバンド**（期間25、±2σ）：`BB_Upper` / `BB_Lower`
  - **3σライン**：`BB_Upper_3sigma`（中間線 + 標準偏差 × 3）
  - **RSI**（期間14）：`RSI`
  - **20日平均出来高**：`Avg_Volume`
  - **%B指標**：`Percent_B`（バンド内での終値の相対位置）

- **`_detect_rsi_entries(df)`**
  RSIが前日≥30 → 当日<30 へ下抜けたインデックスをすべてリストで返します（ステージ1）。

- **`_is_valley_with_lower_shadow(df, i)`**
  指定行が以下の条件をすべて満たす「谷ローソク足」かを判定します（ステージ3）。
  1. 前後の安値より低い（局所最安値 = 谷）
  2. 下ヒゲ ≥ 実体の80%、かつ下ヒゲ率 ≥ 安値の2%
  3. 出来高が20日平均の1.3倍以上（出来高急増）

- **`_check_band_walk_hybrid(df, start_idx, end_idx)`**
  指定期間の50%以上の日で「終値 ≤ -2σ」かつ「安値 ≤ -2σ」を確認します（ステージ2）。

- **`_check_slope_condition(df, rsi_idx, valley_idx)`**
  谷足の翌日の反発幅が、RSI起点からの下落ペースを上回るかを検証します（ステージ3補助）。

- **`_detect_upper_band_exit(row)`**
  当日の高値が +3σ の95%に達し、かつ上ヒゲ（高値の2%以上）が出ているかを判定します（ステージ4）。

- **`_first_entry_after_rsi(df, rsi_idx)`**
  RSI起点より後で最初に「谷条件 + BBウォーク + 傾き条件」をすべて満たす日を探します。

- **`_first_exit_after_entry(df, entry_idx)`**
  エントリー後で最初に上ヒゲ＋3σ到達条件を満たす日を探します。

#### メイン関数

- **`analyze_market_before_stages(chart)`**
  全ステージを一括で評価し、各ステージのパス/不パス、インデックス、カウントなどを辞書形式で返します。

- **`build_market_before_stage_rows(ticker, company_name, chart)`**
  `analyze_market_before_stages` の結果を、専用サマリーCSV用の4行（1ステージ1行）に展開します。各行には `extras` リストで補助情報（RSI値・%B・出来高比率・傾きスコアなど）が付きます。

- **`check_market_before_rule(chart)`**
  既存の `PatternCommand.execute()` インターフェースに合わせた公開API。`{"date", "close", "signal", "extra"}` の辞書を返します。

---

### B. `src/commands.py`（変更）

`check_market_before_rule` のインポートと `MarketBeforeRuleCommand` クラスの追加、および `register_commands` へのコマンド登録が行われました。

```python
# 追加されたインポート
from .strategies.market_before_rule import check_market_before_rule

# 追加されたコマンドクラス
class MarketBeforeRuleCommand(PatternCommand):
    def __init__(self):
        super().__init__("market_beforeルール")

    def execute(self, ticker, chart):
        return check_market_before_rule(chart)

# register_commands に追加
MarketBeforeRuleCommand()
```

---

### C. `src/controller.py`（変更）

`build_market_before_stage_rows` のインポートと、`_make_market_before_stage_summary` メソッドの追加が行われました。

- **`_make_market_before_stage_summary(summary_folder)`**
  全銘柄 × 4ステージのサマリーCSV（`bb_rsi_valley_summary_YYYY-MM-DD.csv`）を `SUMMARY` フォルダに出力します。同名ファイルが存在する場合は `SUMMARY/BK/` フォルダにバックアップします。

---

## 3. シグナル判定ロジックのまとめ

```
RSI30下抜け検出
    ↓ （なければ "No RSI entry"）
BBウォーク＋谷足検出
    ↓ （なければ "No entry"）
＋3σ到達・上ヒゲ検出
    ↓ あれば "ASK"（売り）、なければ "BID"（買い継続）
```

---

## 4. 使用されているライブラリのメソッド解説

### A. TA-Lib（テクニカル分析ライブラリ）

- **`talib.BBANDS(close, timeperiod, nbdevup, nbdevdn, matype)`**
  ボリンジャーバンドの上限・中間・下限を計算します。
  `timeperiod=25`（25日）、`nbdevup=nbdevdn=2`（±2σ）、`matype=0`（単純移動平均）で使用しています。

- **`talib.STDDEV(close, timeperiod)`**
  指定期間の標準偏差を計算します。3σラインの算出に使用します。

- **`talib.RSI(close, timeperiod)`**
  RSI（相対力指数）を計算します。`timeperiod=14`（14日）で使用しています。
  値が30を下回ると売られすぎのシグナルです。

- **`talib.SMA(volume, timeperiod)`**
  単純移動平均を計算します。20日平均出来高の算出に使用しています。

### B. numpy

- **`np.where(condition, x, y)`**
  条件が True の要素に `x`、False の要素に `y` を代入した配列を生成します。
  %B指標の計算でバンド幅が0のときに `nan` を代入するために使用しています。

- **`np.nan`**
  Not a Number（欠損値）を表す定数です。計算不能な箇所のデフォルト値として使用しています。

### C. pandas

- **`df.at[idx, col]`**
  行インデックスと列名を指定して1つの値に高速アクセスします。ループ内の指標値参照に多用されています。

- **`df.iloc[start:end]`**
  位置（整数）でスライスした部分DataFrameを返します。期間内のバンドウォーク集計に使用しています。

- **`pd.notna(val)`**
  値が `NaN` でないかを判定します。指標計算前のデータ有効性チェックに使用しています。

- **`pd.to_datetime(df["Date"])`**
  文字列の日付列を日時型に変換します。日付順のソートに使用しています。
