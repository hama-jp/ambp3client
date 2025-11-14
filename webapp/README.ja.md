# AMB P3 Webダッシュボード

AMB Decoder P3クライアント用のリアルタイムラップタイム表示Webアプリケーションです。

## 概要

FastAPIとWebSocketを使用したリアルタイムダッシュボードで、レース中のラップタイムを即座に表示し、音声で読み上げます。スマートフォン、タブレット、PCなど、あらゆるデバイスのブラウザで動作します。

## 主な機能

### リアルタイム表示
- **WebSocket接続**: 新しいラップタイムを即座に表示（0.5秒ポーリング）
- **自動更新**: データベースを監視し、新しいラップを自動検出
- **接続状態表示**: WebSocket接続のステータスを視覚的に表示

### ラップタイム統計
- **ベストラップ**: 最速ラップタイムを表示
- **平均ラップ**: 平均ラップタイムを計算・表示
- **最新ラップ**: 最後のラップタイムをハイライト表示
- **総周回数**: 合計ラップ数をカウント

### 音声読み上げ
- **Web Speech API対応**: ブラウザの音声合成機能を使用
- **日本語読み上げ**: ラップタイムを日本語で読み上げ
- **ON/OFFボタン**: 音声のオン/オフを簡単に切り替え可能

### トランスポンダー選択
- **複数トランスポンダー対応**: ドロップダウンで表示するトランスポンダーを選択
- **ラジコンカー情報表示**: カー番号とドライバー名を表示（登録されている場合）

### レスポンシブデザイン
- **モバイル対応**: スマートフォンでも見やすいUI
- **タブレット最適化**: iPadなどのタブレットに最適化されたレイアウト
- **ダークモード風**: 目に優しいカラースキーム

## 技術スタック

### バックエンド
- **FastAPI**: 高速なPython Webフレームワーク
- **Uvicorn**: ASGIサーバー
- **WebSocket**: リアルタイム双方向通信
- **MySQL Connector**: データベース接続

### フロントエンド
- **Vanilla JavaScript**: フレームワークなしのシンプルな実装
- **WebSocket API**: リアルタイム通信
- **Web Speech API**: 音声読み上げ
- **CSS3**: モダンなスタイリングとアニメーション

## インストール

### 前提条件

メインプロジェクトのREADME.ja.mdに従って、以下が完了していることを確認してください：
- リポジトリのクローン
- 仮想環境の作成と有効化
- 基本的な依存パッケージのインストール

### 1. 仮想環境の有効化

仮想環境がまだ有効化されていない場合は、有効化します：

Linux/macOSの場合:
```bash
source venv/bin/activate
```

Windowsの場合:
```bash
venv\Scripts\activate
```

### 2. Webアプリ用依存パッケージのインストール

仮想環境を有効化した状態で、Webダッシュボード用のパッケージをインストールします：

```bash
pip install -r requirements-webapp.txt
```

必要なパッケージ：
- `fastapi>=0.104.0`
- `uvicorn>=0.24.0`
- `mysql-connector-python>=8.0.33`
- `pyyaml>=6.0`

### 3. 設定ファイル

プロジェクトルートの`conf.yaml`または`local_conf.yaml`で設定します：

```yaml
mysql_host: 'localhost'
mysql_port: 3306
mysql_db: 'your_database'
mysql_user: 'your_user'
mysql_password: 'your_password'
```

## 起動方法

### 方法1: 起動スクリプトを使用

```bash
./start_webapp.sh
```

### 方法2: 直接起動

```bash
cd webapp
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 方法3: リロード機能付きで開発起動

```bash
cd webapp
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### アクセス

ブラウザで以下のURLにアクセスします：

```
http://localhost:8000
```

ネットワーク上の他のデバイスからアクセスする場合：

```
http://<サーバーのIPアドレス>:8000
```

## 使い方

### 基本的な操作

1. **Webブラウザでアクセス**
   - `http://localhost:8000` を開く

2. **接続状態を確認**
   - 右上の接続ステータスが「接続済み」（緑色）になることを確認

3. **トランスポンダーを選択**
   - ドロップダウンから表示したいトランスポンダーを選択
   - カー番号や名前が登録されている場合は、それも表示されます

4. **ラップタイムを確認**
   - ベストラップ、平均ラップ、最新ラップがリアルタイムで更新されます
   - 新しいラップが記録されると、最新ラップカードが点滅します

5. **音声読み上げ（オプション）**
   - 「音声ON」ボタンをクリックして音声読み上げを有効化
   - 新しいラップが記録されると、ラップタイムが読み上げられます

### ラジコンカー情報の登録

トランスポンダー選択時にカー番号や名前を表示するには、データベースの`cars`テーブルに登録します：

```sql
INSERT INTO cars (transponder_id, name, car_number)
VALUES (123456, '山田太郎', 10);
```

または、既存のトランスポンダーを更新：

```sql
UPDATE cars
SET name = '山田太郎', car_number = 10
WHERE transponder_id = 123456;
```

## API仕様

### REST API エンドポイント

#### `GET /`
メインダッシュボードページを表示

**レスポンス**: HTML

---

#### `GET /api/transponders`
トランスポンダー一覧を取得

**レスポンス**: JSON
```json
[
  {
    "transponder_id": 123456,
    "name": "山田太郎",
    "car_number": 10
  },
  {
    "transponder_id": 234567,
    "name": null,
    "car_number": null
  }
]
```

---

#### `GET /api/laps/{transponder_id}`
指定されたトランスポンダーのラップ統計を取得

**パラメータ**:
- `transponder_id` (int): トランスポンダーID
- `limit` (int, オプション): 取得するラップ数（デフォルト: 50）

**レスポンス**: JSON
```json
{
  "transponder_id": 123456,
  "total_laps": 25,
  "best_lap": 45.234,
  "average_lap": 46.789,
  "latest_lap": 46.123,
  "latest_lap_time": 1699876543210000
}
```

---

### WebSocket エンドポイント

#### `WebSocket /ws`
リアルタイムラップ更新用WebSocket接続

**接続**: `ws://localhost:8000/ws`

**受信メッセージ**:

新しいラップが記録された時：
```json
{
  "type": "new_lap",
  "transponder_id": 123456,
  "lap_time": 46.123,
  "stats": {
    "transponder_id": 123456,
    "total_laps": 26,
    "best_lap": 45.234,
    "average_lap": 46.567,
    "latest_lap": 46.123,
    "latest_lap_time": 1699876543210000
  }
}
```

接続確認（pong）：
```json
{
  "type": "pong"
}
```

**送信メッセージ**:

接続維持（ping）：
```json
"ping"
```

## ディレクトリ構造

```
webapp/
├── app.py                 # FastAPIアプリケーション本体
├── __init__.py
├── static/                # 静的ファイル
│   ├── index.html        # メインHTMLページ
│   ├── css/
│   │   └── style.css     # スタイルシート
│   └── js/
│       └── app.js        # クライアントサイドJavaScript
└── README.ja.md          # このファイル
```

## カスタマイズ

### ポーリング間隔の変更

`app.py`の`monitor_new_laps()`関数内：

```python
# 500ミリ秒ごとにチェック
await asyncio.sleep(0.5)
```

を変更します（例: 1秒間隔にする場合は`1.0`）。

### 取得するラップ数の変更

`app.py`の`get_lap_stats()`関数の`limit`パラメータのデフォルト値を変更：

```python
async def get_lap_stats(transponder_id: int, limit: int = 50):
```

### スタイルのカスタマイズ

`static/css/style.css`を編集して、色やレイアウトを変更できます。

主要なCSS変数：
```css
:root {
  --primary-color: #2c3e50;
  --secondary-color: #3498db;
  --success-color: #27ae60;
  --warning-color: #f39c12;
  --danger-color: #e74c3c;
}
```

## トラブルシューティング

### Webページにアクセスできない

**症状**: ブラウザで接続できない

**解決方法**:
```bash
# サーバーが起動しているか確認
ps aux | grep uvicorn

# ポートが使用されているか確認
lsof -i :8000

# ファイアウォール設定を確認
sudo ufw status
```

---

### WebSocketが接続できない

**症状**: 「接続中...」のまま、「接続済み」にならない

**解決方法**:
1. ブラウザのコンソールでエラーを確認（F12キー）
2. サーバーログを確認
3. プロキシやリバースプロキシがWebSocketをサポートしているか確認

---

### データが表示されない

**症状**: トランスポンダーを選択してもデータが表示されない

**解決方法**:
```bash
# データベース接続を確認
mysql -u <user> -p -h <host> <database>

# lapsテーブルにデータがあるか確認
SELECT * FROM laps ORDER BY rtc_time DESC LIMIT 10;

# amb_client.pyとamb_laps.pyが起動しているか確認
ps aux | grep amb_
```

---

### 音声が再生されない

**症状**: 音声ONにしても読み上げられない

**解決方法**:
1. ブラウザがWeb Speech APIをサポートしているか確認
   - Chrome、Edge、Safariは対応
   - Firefoxは部分的対応
2. ブラウザの音声設定を確認
3. システムの音量を確認
4. ブラウザコンソールでエラーを確認

---

### パフォーマンスの問題

**症状**: 動作が遅い、CPUやメモリ使用率が高い

**解決方法**:
1. データベースのインデックスを確認
   ```sql
   SHOW INDEX FROM laps;
   SHOW INDEX FROM passes;
   ```
2. ポーリング間隔を長くする（0.5秒→1秒など）
3. 取得するラップ数を減らす（50→20など）
4. 古いデータをアーカイブ

## セキュリティに関する注意

### 本番環境での推奨設定

1. **HTTPS/WSS の使用**
   ```bash
   # Nginxやcaddy等のリバースプロキシでSSL/TLS終端
   ```

2. **アクセス制限**
   - ファイアウォールでポートを制限
   - IP制限やBasic認証の追加

3. **環境変数でパスワード管理**
   ```bash
   export MYSQL_PASSWORD="your_password"
   ```
   ```python
   # app.pyで
   password = os.getenv("MYSQL_PASSWORD", "default")
   ```

## 開発

### ローカル開発環境

仮想環境を有効化した状態で開発を行います：

```bash
# 仮想環境を有効化（未実行の場合）
source venv/bin/activate  # Linux/macOS
# または
venv\Scripts\activate     # Windows

# 開発用の依存関係をインストール
pip install -r requirements-dev.txt

# リロード機能付きで起動
cd webapp
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### デバッグモード

`app.py`のログレベルを変更：

```python
logging.basicConfig(
    level=logging.DEBUG,  # INFOからDEBUGに変更
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### 新機能の追加

1. **新しいAPIエンドポイント**: `app.py`に追加
2. **新しいWebSocketイベント**: `monitor_new_laps()`関数を編集
3. **UIの変更**: `static/index.html`、`static/css/style.css`、`static/js/app.js`を編集

## 今後の改善予定

- [ ] ラップタイム履歴グラフ表示
- [ ] 複数トランスポンダーの同時表示
- [ ] ヒート別の表示切り替え
- [ ] エクスポート機能（CSV、PDF）
- [ ] ユーザー認証機能
- [ ] テーマカスタマイズ（ライト/ダークモード切り替え）
- [ ] リーダーボード表示
- [ ] セクタータイム分析

## ライセンス

Apache License 2.0

## サポート

問題が発生した場合は、GitHubのIssuesページで報告してください：
https://github.com/hama-jp/ambp3client/issues
