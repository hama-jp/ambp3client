# AMB P3 Tools

このディレクトリには、AMB P3デコーダーの解析・開発に役立つツールが含まれています。

## record_raw_data.py - 生データ記録ツール

### 概要

AMB P3デコーダーから受信した生のバイナリデータを記録するツールです。
P3プロトコルの公式仕様が公開されていないため、実際のデコーダーの動作を
解析・記録して、プロトコルの理解を深めることができます。

### 機能

- **生データ記録**: デコーダーから受信したバイナリデータをそのまま記録
- **タイムスタンプ付き**: 各レコードに受信時刻を記録
- **デコード結果の併記**: プロトコル解析のためにデコード結果も記録（オプション）
- **JSONL形式**: 1行1レコードで扱いやすい形式
- **安全な停止**: Ctrl+Cで安全に記録を終了

### 記録されるデータ

各レコードには以下の情報が含まれます：

```json
{
  "timestamp": "2025-11-14T12:34:56.789012",
  "record_number": 1,
  "raw_data_hex": "8e010a00f6a40000008f",
  "raw_data_length": 11,
  "decoded": {
    "header": {
      "SOR": "8e",
      "Version": "01",
      "Length": "000a",
      "CRC": "00f6",
      "Flags": "0000",
      "TOR": "00a4"
    },
    "body": {
      "RESULT": {
        "TOR": "GET_TIME",
        "RTC_TIME": "..."
      }
    },
    "decode_success": true
  }
}
```

### 使い方

#### 基本的な使用例

```bash
# 設定ファイルを指定して実行
./tools/record_raw_data.py -f local_conf.yaml
```

このコマンドは、`raw_data_YYYYMMDD_HHMMSS.jsonl` というファイル名で
現在のディレクトリにデータを記録します。

#### 出力ファイルを指定

```bash
./tools/record_raw_data.py -f local_conf.yaml -o captured_data.jsonl
```

#### 生データのみ記録（デコード結果を含めない）

```bash
./tools/record_raw_data.py -f local_conf.yaml --no-decode
```

デコード結果を含めずに生データのみを記録します。
デコード処理のオーバーヘッドを避けたい場合に有用です。

#### デバッグモード

```bash
./tools/record_raw_data.py -f local_conf.yaml -v
```

詳細なログを出力します。接続のトラブルシューティングに便利です。

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|----------|------|----------|
| `-f, --config FILE` | 設定ファイルのパス（必須） | - |
| `-o, --output FILE` | 出力ファイルのパス | `raw_data_YYYYMMDD_HHMMSS.jsonl` |
| `--no-decode` | デコード結果を記録しない | False（デコード結果を記録） |
| `--skip-crc-check` | CRC検証をスキップ | True |
| `-v, --verbose` | 詳細なログを出力 | False |
| `-h, --help` | ヘルプメッセージを表示 | - |

### 記録の停止

記録中に **Ctrl+C** を押すと、安全に記録を停止できます。
既に記録されたデータはファイルに保存されます。

### 出力ファイルの読み取り

記録されたJSONLファイルは、Pythonで簡単に読み取ることができます：

```python
import json

with open('raw_data_20251114_123456.jsonl', 'r') as f:
    for line in f:
        record = json.loads(line)
        print(f"Record {record['record_number']}: {record['raw_data_hex']}")
```

または、`jq`コマンドを使って解析できます：

```bash
# すべてのレコードのタイムスタンプと生データを表示
cat raw_data_20251114_123456.jsonl | jq -r '"\(.timestamp) \(.raw_data_hex)"'

# デコードに成功したレコードのみ抽出
cat raw_data_20251114_123456.jsonl | jq 'select(.decoded.decode_success == true)'

# 特定のTOR（Type of Record）のみ抽出
cat raw_data_20251114_123456.jsonl | jq 'select(.decoded.body.RESULT.TOR == "PASSING")'
```

### 使用例：プロトコル解析

記録した生データを使って、P3プロトコルの理解を深めることができます：

1. **未知のレコードタイプの発見**:
   ```bash
   # デコードに失敗したレコードを抽出
   cat captured_data.jsonl | jq 'select(.decoded.decode_success == false)'
   ```

2. **特定の条件下でのデータ採録**:
   - レース中のPASSINGレコードのパターン
   - デコーダー起動時の初期化シーケンス
   - タイムサーバーとのやり取り

3. **CRC検証の調査**:
   ```bash
   # CRC検証を有効にして記録
   ./tools/record_raw_data.py -f local_conf.yaml --no-skip-crc-check
   ```

### トラブルシューティング

#### デコーダーに接続できない

```
ERROR - デコーダーへの接続に失敗しました: Connection refused to 192.168.1.100:5403
```

- 設定ファイルのIPアドレスとポート番号が正しいか確認してください
- デコーダーがネットワークに接続されているか確認してください
- `ping` や `telnet` でデコーダーへの接続を確認してください

#### ファイルに書き込めない

```
ERROR - データ記録中にエラーが発生しました: Permission denied
```

- 出力ディレクトリへの書き込み権限があるか確認してください
- 絶対パスを指定してみてください

#### デコードエラーが頻発する

```
WARNING - デコードエラー (レコード 42): ...
```

- `--no-decode` オプションを使って生データのみを記録してください
- 記録したデータを後で手動で解析できます

---

## analyze_raw_data.py - 生データ解析ツール

### 概要

`record_raw_data.py`で記録した生データファイル（JSONL形式）を解析・表示するツールです。
記録したデータの内容を確認したり、統計情報を取得したりできます。

### 使い方

#### 基本的な使用例

```bash
# すべてのレコードを表示
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl
```

#### デコード失敗したレコードのみ表示

```bash
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --failed-only
```

未知のレコードタイプや、デコードに失敗したデータを抽出できます。

#### 特定のTORタイプのみ表示

```bash
# PASSINGレコードのみ表示
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --tor PASSING

# GET_TIMEレコードのみ表示
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --tor GET_TIME
```

#### 統計情報を表示

```bash
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --stats
```

以下の統計情報が表示されます：
- 総レコード数
- デコード成功/失敗の割合
- TOR（レコードタイプ）の分布
- データサイズの統計（最小/最大/平均）
- 記録時間と平均レート

#### 表示レコード数を制限

```bash
# 最初の10レコードのみ表示
./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --limit 10
```

### コマンドラインオプション

| オプション | 説明 |
|----------|------|
| `input_file` | 解析する生データファイル（JSONL形式、必須） |
| `--failed-only` | デコード失敗したレコードのみ表示 |
| `--tor TOR` | 特定のTOR（Type of Record）のみ表示 |
| `--stats` | 統計情報のみ表示 |
| `--limit N` | 表示するレコード数を制限 |
| `-h, --help` | ヘルプメッセージを表示 |

### 出力例

```
============================================================
レコード #1
============================================================
タイムスタンプ: 2025-11-14T12:34:56.789012
レコード番号: 1
データ長: 11 バイト
生データ (hex): 8e010a00f6a40000008f

デコード: 成功

ヘッダー:
  SOR: 8e
  Version: 01
  Length: 000a
  CRC: 00f6
  Flags: 0000
  TOR: 00a4

ボディ:
  TOR: GET_TIME
  RTC_TIME: 00012345abcdef
```

### jqコマンドとの併用

JSONLファイルなので、`jq`コマンドと併用すると便利です：

```bash
# すべてのレコードのタイムスタンプと生データを表示
cat raw_data_20251114_123456.jsonl | jq -r '"\(.timestamp) \(.raw_data_hex)"'

# デコードに成功したレコードのみ抽出
cat raw_data_20251114_123456.jsonl | jq 'select(.decoded.decode_success == true)'

# 特定のTORのみ抽出
cat raw_data_20251114_123456.jsonl | jq 'select(.decoded.body.RESULT.TOR == "PASSING")'

# データ長でソート
cat raw_data_20251114_123456.jsonl | jq -s 'sort_by(.raw_data_length)'
```

---

## 関連ファイル

- `AmbP3/decoder.py`: P3プロトコルのデコーダー実装
- `AmbP3/records.py`: レコードタイプの定義
- `amb_client.py`: メインクライアント（参考実装）

## ライセンス

このツールは、ambp3clientプロジェクトと同じライセンス（Apache License 2.0）で提供されます。
