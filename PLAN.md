## リファクタ対象のテクニカル指標

1. **RSI**
  - `talib.RSI(...)` で計算

2. **ボリンジャーバンド上限**
  - `BB_Upper`

3. **ボリンジャーバンド下限**
  - `BB_Lower`

4. **ボリンジャーバンド +3σ ライン**
  - `BB_Upper_3sigma`
  - `middle + std * 3` で算出

5. **20日平均出来高**
  - `Avg_Volume`
  - `talib.SMA(volume, timeperiod=20)` で計算