# AMB Decoder P3 クライアント

ラジコンカーレースやモータースポーツ向けAMBタイミングシステムと連携するPython実装のクライアントです。

## 概要

このクライアントは、AMB Decoder P3デバイスと通信して以下の機能を提供します：

- リアルタイムでトランスポンダーデータを受信
- ラップタイムを自動的に処理
- ヒートセッションとクールダウン期間を管理
- 複数のクライアント間で時刻を同期
- MySQLデータベースへのデータ永続化
- Webダッシュボードでのリアルタイム表示

## 主な機能

- **リアルタイムデータ処理**: AMBデコーダーへの直接TCP接続
- **自動ヒート管理**: 設定可能な継続時間でレースヒートを作成・管理
- **ラップタイム検証**: 最小ラップタイム閾値によるラップタイム検証
- **時刻同期**: マルチデコーダー構成用の内蔵タイムサーバー/クライアント
- **堅牢なエラー処理**: 自動再接続とリトライロジック
- **MySQL統合**: 適切なインデックスを持つパスとラップの保存
- **Webダッシュボード**: FastAPI製のリアルタイムラップタイム表示UI

## システム要件

### 前提条件

- Python 3.7以上
- MySQL/MariaDB 5.7以上
- AMB Decoder P3デバイス
- デコーダーへのネットワーク接続

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/hama-jp/ambp3client
cd ambp3client
```

### 2. 仮想環境の作成と有効化

システムのPython環境を汚さないため、仮想環境の使用を強く推奨します。

**仮想環境の作成:**
```bash
python3 -m venv venv
```

**仮想環境の有効化:**

Linux/macOSの場合:
```bash
source venv/bin/activate
```

Windowsの場合:
```bash
venv\Scripts\activate
```

仮想環境が有効化されると、プロンプトの先頭に `(venv)` が表示されます。

### 3. 依存パッケージのインストール

仮想環境を有効化した状態で、必要なパッケージをインストールします。

**クライアント（基本機能）のみ:**
```bash
pip install -r requirements.txt
```

**Webダッシュボードも含める場合:**
```bash
pip install -r requirements.txt
pip install -r requirements-webapp.txt
```

**開発環境（テスト・リント含む）:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

> **注意:** 仮想環境を終了するには `deactivate` コマンドを実行します。次回起動時には再度 `source venv/bin/activate` で有効化する必要があります。

### 4. データベースのセットアップ

MySQLデータベースとテーブルを作成します：

```bash
mysql -u root -p < schema
```

スキーマには以下のテーブルが含まれます：
- `passes`: トランスポンダー通過記録
- `laps`: 処理されたラップタイム
- `heats`: レースセッション
- `cars`: ラジコンカー/トランスポンダー情報
- `settings`: システム設定

## 設定

### 設定ファイルの作成

`local_conf.yaml`を作成します：

```yaml
# デコーダー接続設定
ip: '192.168.1.100'           # デコーダーのIPアドレス
port: 5403                     # デコーダーのポート（デフォルト: 5403）

# MySQL設定
mysql_host: 'localhost'
mysql_user: 'your_user'
mysql_db: 'your_database'
mysql_password: 'your_password'  # 本番環境では環境変数を使用してください
mysql_port: 3306
mysql_backend: true

# ログファイル
file: '/tmp/amb_raw.log'       # 生データログ
debug_file: '/tmp/amb_debug.log'  # デバッグログ

# ヒート設定（オプション）
heat_duration: 480             # ヒートの継続時間（秒）
heat_cooldown: 90              # ヒート終了後のクールダウン期間（秒）
minimum_lap_time: 10           # 有効な最小ラップタイム（秒）

# CRC検証（オプション）
skip_crc_check: true           # CRC検証をスキップ（デフォルト: true）
```

### 設定オプション

| オプション | 説明 | デフォルト値 |
|--------|-------------|---------|
| `skip_crc_check` | CRC検証をスキップ（一部のデコーダーはCRCを0x0000として送信） | true |
| `heat_duration` | ヒートの継続時間（秒） | 480 |
| `heat_cooldown` | ヒート後のクールダウン期間（秒） | 90 |
| `minimum_lap_time` | 有効な最小ラップタイム（秒） | 10 |

### CRC検証について

デフォルトでは、CRC検証は**無効**（`skip_crc_check: true`）になっています。これは、CRC値を0x0000として送信する可能性のあるデコーダーとの互換性を最大化するためです。厳密なCRC検証を有効にするには、設定ファイルで`skip_crc_check: false`を設定してください。

## 使い方

### 基本的な起動手順

#### 1. デコーダークライアントの起動

デコーダーからデータを受信し、データベースに書き込みます：

```bash
./amb_client.py -f local_conf.yaml
```

#### 2. ラッププロセッサーの起動

ヒートとラップを処理します：

```bash
./amb_laps.py
```

#### 3. Webダッシュボードの起動（オプション）

リアルタイムでラップタイムを表示します：

```bash
./start_webapp.sh
```

または直接起動：

```bash
cd webapp
uvicorn app:app --host 0.0.0.0 --port 8000
```

Webブラウザで `http://localhost:8000` にアクセスすると、リアルタイムダッシュボードが表示されます。

## アーキテクチャ

### コアコンポーネント

- **amb_client.py**: デコーダーに接続してパスデータをデータベースに書き込むメインクライアント
- **amb_laps.py**: ヒートとラップの処理ロジック
- **webapp/app.py**: FastAPI製のWebダッシュボード（WebSocket対応）

### ライブラリモジュール

- **AmbP3/decoder.py**: AMB P3バイナリフォーマット用のプロトコルデコーダー
- **AmbP3/write.py**: カーソル管理を含むデータベース書き込み操作
- **AmbP3/time_server.py / time_client.py**: クライアント間の時刻同期
- **AmbP3/config.py**: 設定ファイル読み込みと引数処理
- **AmbP3/crc16.py**: CRC16チェックサム計算
- **AmbP3/records.py**: データレコード定義

## Webダッシュボード

WebダッシュボードはFastAPIとWebSocketを使用したリアルタイム表示システムです。

### 機能

- **リアルタイム更新**: WebSocketによる即座のラップタイム表示
- **統計表示**: 各トランスポンダーのベストラップ、平均ラップ、最新ラップ
- **ラジコンカー情報**: カー番号とドライバー名の表示
- **音声読み上げ対応**: Web Speech APIによるラップタイム読み上げ（ブラウザ対応時）

### API エンドポイント

- `GET /`: ダッシュボードメインページ
- `GET /api/transponders`: トランスポンダー一覧取得
- `GET /api/laps/{transponder_id}`: 指定トランスポンダーのラップ統計
- `WebSocket /ws`: リアルタイムラップ更新用WebSocket接続

詳細は [webapp/README.ja.md](webapp/README.ja.md) を参照してください。

## データフロー

```
AMB Decoder P3
    ↓ (TCP/IP)
amb_client.py
    ↓ (MySQL)
passes テーブル
    ↓
amb_laps.py
    ↓ (MySQL)
laps/heats テーブル
    ↓
webapp/app.py (FastAPI)
    ↓ (WebSocket)
Webブラウザ
```

## ヒート管理

### ヒートのライフサイクル

1. **グリーンフラグ待機**: `settings`テーブルの`green_flag=1`を待機
2. **ヒート開始**: 最初のパスで自動的にヒートを作成
3. **ラップ記録**: `heat_duration`秒間、すべてのパスを記録
4. **イエローフラグ**: ヒート終了時刻になるとフラグを振る
5. **クールダウン**: `heat_cooldown`秒間、追加のラップを記録
6. **ヒート終了**: すべての参加者が終了するか、最大時間に到達

### グリーンフラグの設定

レースを開始するには、データベースでグリーンフラグを設定します：

```sql
UPDATE settings SET value='1' WHERE setting='green_flag';
```

ヒートが終了したら、次のレースのためにリセットします：

```sql
UPDATE settings SET value='0' WHERE setting='green_flag';
```

## トラブルシューティング

### デコーダーに接続できない

```bash
# デコーダーへの接続を確認
ping <decoder_ip>

# ポートが開いているか確認
telnet <decoder_ip> 5403
```

### MySQLエラー

```bash
# データベースとテーブルが存在することを確認
mysql -u <user> -p <database> -e "SHOW TABLES;"

# 接続設定を確認
mysql -u <user> -p -h <host> -P <port> <database>
```

### CRCエラー

設定ファイルで`skip_crc_check: true`を設定してCRC検証を無効にしてください。

### Webダッシュボードが起動しない

```bash
# 依存パッケージがインストールされているか確認
pip install -r requirements-webapp.txt

# ポート8000が使用可能か確認
lsof -i :8000
```

## 開発

### テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジレポート付き
pytest --cov=AmbP3 --cov-report=html

# 特定のテストのみ
pytest tests/unit/test_decoder.py
```

### コード品質チェック

```bash
# Flake8 (リンター)
flake8 AmbP3/ tests/

# Bandit (セキュリティチェック)
bandit -r AmbP3/

# Black (コードフォーマット)
black --check AmbP3/ tests/
```

### 開発ツール

#### 生データ記録ツール

P3プロトコルの公式仕様が公開されていないため、実際のデコーダーの生データを記録・解析するツールが用意されています。

```bash
# デコーダーの生データを記録
./tools/record_raw_data.py -f local_conf.yaml

# 出力ファイルを指定
./tools/record_raw_data.py -f local_conf.yaml -o captured_data.jsonl
```

詳細は [tools/README.md](tools/README.md) を参照してください。

## データベーススキーマ

### passes テーブル
生のトランスポンダー通過記録を保存します。

| カラム | 型 | 説明 |
|--------|-----|------|
| db_entry_id | INT | 自動インクリメントID |
| pass_id | INT | パスID（ユニーク） |
| transponder_id | INT | トランスポンダーID |
| rtc_time | BIGINT | リアルタイムクロックタイムスタンプ（マイクロ秒） |
| strength | INT | 信号強度 |
| hits | INT | ヒット数 |
| flags | INT | フラグ |
| decoder_id | INT | デコーダーID |

### laps テーブル
処理済みのラップタイムを保存します。

| カラム | 型 | 説明 |
|--------|-----|------|
| heat_id | INT | ヒートID |
| pass_id | INT | パスID（passes.pass_idへの参照） |
| transponder_id | INT | トランスポンダーID |
| rtc_time | BIGINT | ラップ時刻 |

### heats テーブル
レースセッション情報を保存します。

| カラム | 型 | 説明 |
|--------|-----|------|
| heat_id | INT | 自動インクリメントID |
| heat_finished | TINYINT | 終了フラグ（0=実行中、1=終了） |
| first_pass_id | INT | 最初のパスID |
| last_pass_id | INT | 最後のパスID |
| rtc_time_start | BIGINT | 開始時刻 |
| rtc_time_end | BIGINT | 終了時刻 |
| race_flag | INT | レースフラグ（0=緑、1=黄、2=チェッカー） |
| rtc_time_max_end | BIGINT | 最大終了時刻（クールダウン含む） |

## よくある質問

### Q: 複数のデコーダーを使用できますか？
A: はい。time_serverとtime_clientを使用して、複数のデコーダー間で時刻を同期できます。

### Q: カー番号や名前を設定するには？
A: `cars`テーブルにトランスポンダーIDとラジコンカー情報を登録します：

```sql
INSERT INTO cars (transponder_id, name, car_number)
VALUES (123456, 'ドライバー名', 10);
```

### Q: 最小ラップタイムを変更するには？
A: 設定ファイルで`minimum_lap_time`を変更するか、データベースの`settings`テーブルで変更します：

```sql
UPDATE settings SET value='15' WHERE setting='minimum_lap_time';
```

### Q: ログファイルが大きくなりすぎる場合は？
A: logrotateなどを使用してログローテーションを設定してください。

## 関連プロジェクト

- [AMB Web Interface](https://github.com/vmindru/ambweb)
- [AMB Docker Setup](https://github.com/br0ziliy/amb-docker)

## ライセンス

Apache License 2.0

## サポート

問題が発生した場合は、GitHubのIssuesページで報告してください：
https://github.com/hama-jp/ambp3client/issues

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## セキュリティ

セキュリティの脆弱性を発見した場合は、公開issueではなく、プロジェクトメンテナーに直接報告してください。
