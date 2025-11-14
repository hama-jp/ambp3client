# AMB P3 Live Decoder Simulation - 実装提案書

## 概要

現在のtest_server.pyは静的なヘキサデータファイルを再生するだけで、実際のレース状況を再現できません。この提案では、よりライブっぽい（現実的な）デコーダーシミュレーションを実現するための新しい`live_test_server.py`の実装を提案します。

## 現状の問題点

### test_server.pyの制限

1. **タイムスタンプが固定**
   - ファイル内のRTC_TIME/UTC_TIMEは過去の固定値
   - 現在時刻と同期していないためGET_TIME処理が不自然

2. **パターンが単調**
   - 同じ1,388行のデータを繰り返し再生
   - 実際のレースのような予測不可能性がない

3. **レースシナリオ未対応**
   - 複数トランスポンダーの同時走行を表現できない
   - 追い抜き、周回遅れ等のイベントが発生しない

4. **信号品質が固定**
   - STRENGTH、HITSが常に同じ値
   - 実機では距離や速度で変動する

5. **STATUS送信が不規則**
   - 実機は約1秒間隔でSTATUSを送信
   - テストデータではパターンがランダム

## 提案: live_test_server.py

### アーキテクチャ

```
┌─────────────────────────────────────┐
│     live_test_server.py             │
├─────────────────────────────────────┤
│  1. ScenarioManager                 │
│     - レースシナリオ管理            │
│     - タイムライン制御              │
│                                     │
│  2. TransponderSimulator           │
│     - 各トランスポンダーの動き     │
│     - ラップタイム生成              │
│     - 位置計算                      │
│                                     │
│  3. MessageBuilder                  │
│     - P3メッセージ生成              │
│     - CRC計算                       │
│     - エスケープ処理                │
│                                     │
│  4. DecoderSimulator                │
│     - TCPサーバー                   │
│     - メッセージ送信制御            │
│     - STATUS定期送信                │
└─────────────────────────────────────┘
```

### 主要機能

#### 1. 動的タイムスタンプ生成

**仕様**:
- RTC_TIME: システム時刻をマイクロ秒単位で取得（8バイト、リトルエンディアン）
- UTC_TIME: UNIX時刻（8バイト、リトルエンディアン）
- GET_TIMEリクエストに対して現在時刻を返答

**実装例**:
```python
import time

def get_rtc_time_microseconds():
    """現在時刻をマイクロ秒単位で取得（RTC_TIME用）"""
    return int(time.time() * 1_000_000)

def get_utc_time():
    """UNIX時刻を取得（UTC_TIME用）"""
    return int(time.time())
```

#### 2. マルチトランスポンダーシミュレーション

**仕様**:
```python
class TransponderConfig:
    transponder_id: int      # トランスポンダーID
    avg_lap_time: float      # 平均ラップタイム（秒）
    variance: float          # ラップタイムのばらつき（秒）
    start_delay: float       # スタート遅延（秒）

class RaceScenario:
    transponders: List[TransponderConfig]
    track_length: float      # トラック長（メートル）
    duration: int            # レース時間（秒）
```

**例**:
```python
# 3台のトランスポンダーでレースをシミュレーション
scenario = RaceScenario(
    transponders=[
        TransponderConfig(id=123456, avg_lap_time=25.5, variance=0.3, start_delay=0.0),
        TransponderConfig(id=234567, avg_lap_time=27.2, variance=0.5, start_delay=0.2),
        TransponderConfig(id=345678, avg_lap_time=29.8, variance=0.8, start_delay=0.5),
    ],
    track_length=100.0,
    duration=480  # 8分間
)
```

#### 3. 現実的な信号特性

**PASSING メッセージフィールド**:

| フィールド | 生成方法 | 備考 |
|-----------|----------|------|
| PASSING_NUMBER | インクリメント | デコーダー起動からの通算検出回数 |
| TRANSPONDER | シナリオから | トランスポンダーID（4バイト） |
| RTC_TIME | 動的生成 | 現在のマイクロ秒タイムスタンプ |
| STRENGTH | 距離ベース | 0-1023、アンテナ近傍で最大 |
| HITS | 速度ベース | 1-6、速い車ほど少ない |
| FLAGS | 固定/ランダム | バッテリー状態等 |
| UTC_TIME | 動的生成 | UNIX時刻 |

**信号強度計算アルゴリズム**:
```python
def calculate_strength(distance_from_antenna: float) -> int:
    """
    アンテナからの距離に基づいて信号強度を計算

    Args:
        distance_from_antenna: アンテナからの距離（メートル）

    Returns:
        信号強度 (0-1023)
    """
    # 距離が0mで最大強度、2m以上で最小強度
    max_strength = 1023
    min_strength = 200
    max_distance = 2.0

    if distance_from_antenna >= max_distance:
        return min_strength

    # 逆二乗則を簡易的に適用
    ratio = 1.0 - (distance_from_antenna / max_distance)
    strength = int(min_strength + (max_strength - min_strength) * ratio)

    # ノイズを追加（±5%）
    noise = random.randint(-50, 50)
    return max(min_strength, min(max_strength, strength + noise))

def calculate_hits(speed_mps: float) -> int:
    """
    通過速度に基づいてヒット数を計算

    Args:
        speed_mps: 速度（メートル毎秒）

    Returns:
        ヒット数 (1-6)
    """
    # 速度が遅いほどヒット数が多い
    # 5 m/s: 6ヒット, 15 m/s: 2ヒット
    if speed_mps <= 5.0:
        return 6
    elif speed_mps <= 8.0:
        return 5
    elif speed_mps <= 10.0:
        return 4
    elif speed_mps <= 12.0:
        return 3
    else:
        return 2
```

#### 4. 定期STATUSメッセージ

**仕様**:
- 送信間隔: 1.0秒（実機の挙動に合わせる）
- PASSINGメッセージと非同期で送信
- フィールド値を現実的な範囲で変動

**STATUS フィールド**:

| フィールド | 範囲 | 説明 |
|-----------|------|------|
| NOISE | 20-50 | 環境ノイズレベル |
| GPS | 0-1 | GPS同期状態（0=未同期、1=同期済） |
| TEMPERATURE | 25-45 | デコーダー内部温度（℃） |
| INPUT_VOLTAGE | 115-125 | 入力電圧（12V±10%を表現） |
| LOOP_TRIGGERS | 0-10 | ループトリガー回数（1秒間） |

**実装例**:
```python
import threading

class StatusSender:
    def __init__(self, connection, interval=1.0):
        self.connection = connection
        self.interval = interval
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._send_loop, daemon=True)
        self.thread.start()

    def _send_loop(self):
        while self.running:
            status_msg = self._build_status_message()
            self.connection.send(status_msg)
            time.sleep(self.interval)

    def _build_status_message(self):
        # STATUS (TOR=0x0002) メッセージを生成
        fields = {
            "NOISE": random.randint(20, 50),
            "GPS": 1,  # 常にGPS同期と仮定
            "TEMPERATURE": random.randint(25, 45),
            "INPUT_VOLTAGE": random.randint(115, 125),
            "LOOP_TRIGGERS": random.randint(0, 10),
        }
        return build_p3_message(tor=0x0002, fields=fields)
```

#### 5. レースイベントシミュレーション

**タイムライン制御**:
```python
class RaceEvent:
    timestamp: float      # イベント発生時刻（レース開始からの秒数）
    event_type: str       # "GREEN_FLAG", "YELLOW_FLAG", etc.
    data: dict            # イベント固有データ

timeline = [
    RaceEvent(0, "GREEN_FLAG", {}),
    RaceEvent(300, "YELLOW_FLAG", {"reason": "incident"}),
    RaceEvent(330, "GREEN_FLAG", {}),
    RaceEvent(480, "CHECKERED_FLAG", {}),
]
```

**グリーンフラッグ処理**:
- データベースの`settings`テーブルを監視（オプション）
- 手動でフラッグを設定可能
- amb_laps.pyのヒート管理と連携

#### 6. コマンドライン引数

```bash
./live_test_server.py [OPTIONS]

Options:
  -l, --listen-address TEXT   Bind address [default: 127.0.0.1]
  -p, --listen-port INTEGER   Bind port [default: 12001]
  -s, --scenario FILE         Scenario YAML file
  -d, --duration INTEGER      Race duration in seconds [default: 480]
  -v, --verbose              Enable verbose logging
  --status-interval FLOAT     STATUS message interval [default: 1.0]
```

**シナリオファイル例** (`scenario.yaml`):
```yaml
# レースシナリオ定義
track:
  length: 100.0  # メートル
  name: "Test Track"

transponders:
  - id: 123456
    name: "Car #1"
    avg_lap_time: 25.5
    variance: 0.3
    start_delay: 0.0

  - id: 234567
    name: "Car #2"
    avg_lap_time: 27.2
    variance: 0.5
    start_delay: 0.2

  - id: 345678
    name: "Car #3"
    avg_lap_time: 29.8
    variance: 0.8
    start_delay: 0.5

timeline:
  - timestamp: 0
    event: "GREEN_FLAG"

  - timestamp: 480
    event: "YELLOW_FLAG"

  - timestamp: 570
    event: "CHECKERED_FLAG"

decoder:
  decoder_id: 0x04131804  # DECODER_ID (4バイト)
  status_interval: 1.0
  noise_level: [20, 50]   # ノイズ範囲
  temperature: [25, 35]   # 温度範囲（℃）
```

### メッセージ生成の詳細

#### P3メッセージビルダー

```python
from AmbP3 import crc16

class P3MessageBuilder:
    """AMB P3プロトコルメッセージを生成"""

    VERSION = 0x02
    SOR = 0x8E
    EOR = 0x8F

    @staticmethod
    def build_passing(passing_number, transponder_id, rtc_time,
                     strength, hits, flags, utc_time, decoder_id):
        """PASSING (0x0001) メッセージを生成"""
        body = bytearray()

        # TOR (Type of Record)
        body.extend((0x01, 0x00))  # 0x0001 (little-endian)

        # PASSING_NUMBER (0x01)
        body.extend([0x01, 0x04])  # Field ID, Length
        body.extend(passing_number.to_bytes(4, 'little'))

        # TRANSPONDER (0x03)
        body.extend([0x03, 0x04])
        body.extend(transponder_id.to_bytes(4, 'little'))

        # RTC_TIME (0x04)
        body.extend([0x04, 0x08])
        body.extend(rtc_time.to_bytes(8, 'little'))

        # STRENGTH (0x05)
        body.extend([0x05, 0x02])
        body.extend(strength.to_bytes(2, 'little'))

        # HITS (0x06)
        body.extend([0x06, 0x02])
        body.extend(hits.to_bytes(2, 'little'))

        # FLAGS (0x08)
        body.extend([0x08, 0x02])
        body.extend(flags.to_bytes(2, 'little'))

        # UTC_TIME (0x10) - オプション
        if utc_time is not None:
            body.extend([0x10, 0x08])
            body.extend(utc_time.to_bytes(8, 'little'))

        # DECODER_ID (0x81) - General field
        body.extend([0x81, 0x04])
        body.extend(decoder_id.to_bytes(4, 'little'))

        return P3MessageBuilder._build_message(body)

    @staticmethod
    def build_status(noise, gps, temperature, voltage, loop_triggers, decoder_id):
        """STATUS (0x0002) メッセージを生成"""
        body = bytearray()

        # TOR
        body.extend((0x02, 0x00))  # 0x0002

        # NOISE (0x01)
        body.extend([0x01, 0x02])
        body.extend(noise.to_bytes(2, 'little'))

        # GPS (0x06)
        body.extend([0x06, 0x01])
        body.extend([gps])

        # TEMPERATURE (0x07)
        body.extend([0x07, 0x02])
        body.extend(temperature.to_bytes(2, 'little'))

        # INPUT_VOLTAGE (0x0c)
        body.extend([0x0c, 0x01])
        body.extend([voltage])

        # LOOP_TRIGGERS (0x0b)
        body.extend([0x0b, 0x02])
        body.extend(loop_triggers.to_bytes(2, 'little'))

        # DECODER_ID (0x81)
        body.extend([0x81, 0x04])
        body.extend(decoder_id.to_bytes(4, 'little'))

        return P3MessageBuilder._build_message(body)

    @staticmethod
    def _build_message(body):
        """共通のメッセージ構築処理（ヘッダー追加、CRC計算、エスケープ）"""
        # ヘッダー構築
        message = bytearray()
        message.append(P3MessageBuilder.SOR)     # SOR
        message.append(P3MessageBuilder.VERSION) # Version

        # Flags (仮に0x0000)
        flags = 0x0000

        # Length計算（SORからEORまで）
        length = 1 + 1 + 2 + 2 + 2 + len(body) + 1  # SOR + VER + LEN + CRC + FLAGS + BODY + EOR
        message.extend(length.to_bytes(2, 'little'))

        # CRC placeholder
        crc_pos = len(message)
        message.extend([0x00, 0x00])

        # Flags
        message.extend(flags.to_bytes(2, 'little'))

        # Body
        message.extend(body)

        # EOR
        message.append(P3MessageBuilder.EOR)

        # CRC計算
        message_for_crc = bytearray(message)
        message_for_crc[crc_pos:crc_pos+2] = [0x00, 0x00]

        crc_table = crc16.table()
        calculated_crc = crc16.calc(message_for_crc.hex(), crc_table)

        # CRCをbig-endianで挿入
        message[crc_pos:crc_pos+2] = calculated_crc.to_bytes(2, 'big')

        # エスケープ処理
        return P3MessageBuilder._escape(bytes(message))

    @staticmethod
    def _escape(data):
        """エスケープ処理を適用"""
        escaped = bytearray()
        escaped.append(data[0])  # SOR

        for byte in data[1:-1]:  # SORとEOR以外
            if byte in [0x8D, 0x8E, 0x8F]:
                escaped.append(0x8D)
                escaped.append(byte + 0x20)
            else:
                escaped.append(byte)

        escaped.append(data[-1])  # EOR
        return bytes(escaped)
```

### クラス設計

#### 1. TransponderSimulator

```python
import random
import time

class TransponderSimulator:
    """1つのトランスポンダーの動きをシミュレート"""

    def __init__(self, config: TransponderConfig, track_length: float):
        self.config = config
        self.track_length = track_length
        self.position = 0.0  # 現在位置（メートル）
        self.lap_count = 0
        self.race_start_time = None
        self.last_passing_time = None

    def start_race(self, start_time: float):
        """レース開始"""
        self.race_start_time = start_time + self.config.start_delay
        self.position = 0.0
        self.lap_count = 0
        self.last_passing_time = None

    def update(self, current_time: float) -> List[dict]:
        """
        現在時刻での状態を更新し、通過イベントを返す

        Returns:
            通過イベントのリスト（空の場合もあり）
        """
        if self.race_start_time is None or current_time < self.race_start_time:
            return []

        elapsed = current_time - self.race_start_time

        # 現在のラップタイムを計算（ばらつきを含む）
        lap_time = self._calculate_lap_time()

        # 現在完了しているべきラップ数
        expected_laps = int(elapsed / lap_time)

        events = []

        # 未記録のラップがあれば通過イベントを生成
        while self.lap_count < expected_laps:
            self.lap_count += 1
            passing_time = self.race_start_time + (self.lap_count * lap_time)

            # 現実的な信号パラメータを計算
            speed = self.track_length / lap_time  # m/s
            strength = calculate_strength(random.uniform(0.0, 0.5))
            hits = calculate_hits(speed)

            events.append({
                "transponder_id": self.config.transponder_id,
                "time": passing_time,
                "lap": self.lap_count,
                "strength": strength,
                "hits": hits,
                "flags": 0x0000,
            })

            self.last_passing_time = passing_time

        return events

    def _calculate_lap_time(self) -> float:
        """ラップタイムを計算（ばらつきを含む）"""
        # 正規分布でばらつきを追加
        variance = random.gauss(0, self.config.variance)
        return self.config.avg_lap_time + variance
```

#### 2. ScenarioManager

```python
class ScenarioManager:
    """レースシナリオ全体を管理"""

    def __init__(self, scenario: RaceScenario):
        self.scenario = scenario
        self.transponders = [
            TransponderSimulator(config, scenario.track_length)
            for config in scenario.transponders
        ]
        self.start_time = None
        self.passing_number = 0

    def start(self):
        """レース開始"""
        self.start_time = time.time()
        for transponder in self.transponders:
            transponder.start_race(self.start_time)

    def get_events(self) -> List[dict]:
        """
        現在時刻での全イベントを取得

        Returns:
            通過イベントのリスト（時系列順）
        """
        current_time = time.time()
        all_events = []

        for transponder in self.transponders:
            events = transponder.update(current_time)
            all_events.extend(events)

        # 時刻順にソート
        all_events.sort(key=lambda e: e["time"])

        return all_events
```

#### 3. LiveDecoderServer

```python
import socket
import threading

class LiveDecoderServer:
    """ライブデコーダーシミュレーションサーバー"""

    def __init__(self, host: str, port: int, scenario: RaceScenario):
        self.host = host
        self.port = port
        self.scenario_manager = ScenarioManager(scenario)
        self.message_builder = P3MessageBuilder()
        self.decoder_id = 0x04131804
        self.running = False
        self.conn = None

    def start(self):
        """サーバー起動"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)

        print(f"Live decoder server listening on {self.host}:{self.port}")

        self.conn, addr = server_socket.accept()
        print(f"Client connected: {addr}")

        self.running = True

        # STATUS送信スレッドを起動
        status_thread = threading.Thread(target=self._status_loop, daemon=True)
        status_thread.start()

        # レース開始
        self.scenario_manager.start()

        # PASSING送信ループ
        self._passing_loop()

    def _passing_loop(self):
        """PASSINGメッセージ送信ループ"""
        last_event_time = 0.0

        while self.running:
            events = self.scenario_manager.get_events()

            for event in events:
                # 既に送信済みのイベントはスキップ
                if event["time"] <= last_event_time:
                    continue

                # PASSINGメッセージを生成・送信
                self.passing_number += 1

                msg = self.message_builder.build_passing(
                    passing_number=self.passing_number,
                    transponder_id=event["transponder_id"],
                    rtc_time=int(event["time"] * 1_000_000),
                    strength=event["strength"],
                    hits=event["hits"],
                    flags=event["flags"],
                    utc_time=int(event["time"]),
                    decoder_id=self.decoder_id
                )

                try:
                    self.conn.send(msg)
                    print(f"PASSING #{self.passing_number}: Transponder {event['transponder_id']}, Lap {event['lap']}")
                except (BrokenPipeError, ConnectionResetError):
                    print("Connection lost")
                    self.running = False
                    break

                last_event_time = event["time"]

            time.sleep(0.1)  # 100msごとにチェック

    def _status_loop(self):
        """STATUSメッセージ定期送信"""
        while self.running:
            msg = self.message_builder.build_status(
                noise=random.randint(20, 50),
                gps=1,
                temperature=random.randint(25, 45),
                voltage=random.randint(115, 125),
                loop_triggers=random.randint(0, 10),
                decoder_id=self.decoder_id
            )

            try:
                self.conn.send(msg)
            except (BrokenPipeError, ConnectionResetError):
                break

            time.sleep(1.0)  # 1秒間隔
```

## 実装計画

### フェーズ1: 基本機能（推奨実装範囲）

1. ✅ 動的タイムスタンプ生成
2. ✅ マルチトランスポンダーシミュレーション（固定シナリオ）
3. ✅ 現実的なSTRENGTH/HITS計算
4. ✅ 定期STATUS送信
5. ✅ コマンドライン引数サポート

**所要時間**: 4-6時間

### フェーズ2: 高度な機能（オプション）

1. ⚠️ YAMLシナリオファイルサポート
2. ⚠️ レースイベント制御（フラグ等）
3. ⚠️ SIGNALS メッセージ実装
4. ⚠️ リアルタイム制御（WebSocket等）

**所要時間**: 8-12時間

### フェーズ3: テストと統合

1. 統合テスト追加
2. 既存のamb_client.py、amb_laps.pyとの動作確認
3. ドキュメント更新

**所要時間**: 2-4時間

## 使用例

### 基本的な使い方

```bash
# デフォルト設定で起動（3台のトランスポンダー、8分間レース）
./live_test_server.py

# カスタムポートで起動
./live_test_server.py -p 5403

# シナリオファイルを使用
./live_test_server.py -s scenarios/5car_race.yaml

# 詳細ログ表示
./live_test_server.py -v
```

### amb_client.pyと組み合わせて使う

```bash
# Terminal 1: Live test server起動
./live_test_server.py -p 5403

# Terminal 2: AMB client起動
./amb_client.py -f local_conf.yaml

# Terminal 3: Lap processor起動
./amb_laps.py

# Terminal 4: Web dashboard起動
cd webapp && uvicorn app:app --host 0.0.0.0 --port 8000
```

### 出力例

```
Live decoder server listening on 127.0.0.1:12001
Client connected: ('127.0.0.1', 54321)
PASSING #1: Transponder 123456, Lap 1, Strength 892, Hits 3
STATUS: Noise=32, Temp=28°C, Voltage=120
PASSING #2: Transponder 234567, Lap 1, Strength 756, Hits 4
PASSING #3: Transponder 345678, Lap 1, Strength 623, Hits 5
PASSING #4: Transponder 123456, Lap 2, Strength 915, Hits 3
STATUS: Noise=35, Temp=29°C, Voltage=118
...
```

## テスト計画

### 単体テスト

```python
# tests/unit/test_live_server.py

def test_transponder_simulator_lap_generation():
    """ラップ生成が正しく動作するか"""
    config = TransponderConfig(id=123, avg_lap_time=25.0, variance=0.5, start_delay=0.0)
    sim = TransponderSimulator(config, track_length=100.0)

    sim.start_race(time.time())
    time.sleep(26)  # 1ラップ以上待つ

    events = sim.update(time.time())
    assert len(events) >= 1
    assert events[0]["transponder_id"] == 123

def test_message_builder_passing():
    """PASSINGメッセージ生成が正しいか"""
    msg = P3MessageBuilder.build_passing(
        passing_number=1,
        transponder_id=123456,
        rtc_time=1234567890000000,
        strength=800,
        hits=3,
        flags=0,
        utc_time=1234567890,
        decoder_id=0x04131804
    )

    # デコードしてフィールドを確認
    header, body = p3decode(msg, skip_crc_check=False)
    assert header["TOR"] == "PASSING"
    assert body["RESULT"]["TRANSPONDER"] == "0001e240"  # 123456 in hex
```

### 統合テスト

```python
# tests/integration/test_live_server_integration.py

def test_live_server_with_amb_client():
    """live_test_serverとamb_clientの統合テスト"""
    # Live serverを起動
    scenario = RaceScenario(...)
    server = LiveDecoderServer("127.0.0.1", 0, scenario)

    # Connectionで接続
    conn = Connection("127.0.0.1", server.port)
    conn.connect()

    # PASSINGメッセージを受信
    messages = conn.read()
    assert len(messages) > 0

    header, body = p3decode(messages[0])
    assert header["TOR"] == "PASSING"
```

## まとめ

### メリット

1. ✅ **現実的なテスト環境** - 実機がなくても開発・デバッグが可能
2. ✅ **再現性** - シナリオファイルで同じ状況を繰り返しテスト
3. ✅ **柔軟性** - 様々なレース状況（密集、周回遅れ等）を簡単にシミュレーション
4. ✅ **教育目的** - P3プロトコルの理解を深めるツールとして有用
5. ✅ **CI/CD対応** - 自動テストに組み込み可能

### 今後の拡張案

- WebUIでシナリオをリアルタイム制御
- 実際のトラックレイアウトを考慮した位置シミュレーション
- GPS座標のシミュレーション（GPS_INFOメッセージ）
- デコーダー障害シミュレーション（接続断、CRCエラー等）
- 複数デコーダーの同時シミュレーション

## 参考資料

- [AMB P3 Protocol Documentation](./P3_PROTOCOL.md)
- [AmbP3/records.py](../AmbP3/records.py) - メッセージタイプ定義
- [test_server.py](../test_server.py) - 既存のテストサーバー実装
- [AMB公式サイト](https://www.amb-it.com/)
