# AMB P3 Protocol Implementation Guide

このドキュメントは、AMB Decoder P3プロトコルの実装に関する詳細な技術情報を提供します。

## 目次

1. [プロトコル概要](#プロトコル概要)
2. [メッセージ構造](#メッセージ構造)
3. [CRC16検証](#crc16検証)
4. [エスケープ処理](#エスケープ処理)
5. [実装の詳細](#実装の詳細)
6. [トラブルシューティング](#トラブルシューティング)

---

## プロトコル概要

AMB P3プロトコルは、AMB Decoderデバイスとクライアント間でトランスポンダーデータを送受信するためのバイナリプロトコルです。

### 主な特徴

- バイナリフォーマット
- CRC16チェックサムによるデータ整合性保証
- エスケープシーケンスによる特殊バイトの処理
- 複数のメッセージタイプ（PASSING、GET_TIME、STATUS等）

---

## メッセージ構造

### 基本フォーマット

```
+------+------+------+------+------+------+------+------+------+-----+------+
| SOR  | VER  | LEN1 | LEN2 | CRC1 | CRC2 | FLG1 | FLG2 | TOR1 | ... | EOR  |
+------+------+------+------+------+------+------+------+------+-----+------+
  0x8E   0x01-02      (2 bytes)    (2 bytes)    (2 bytes)   (var)   0x8F
```

### フィールド詳細

| フィールド | サイズ | 説明 | エンディアン |
|------------|--------|------|--------------|
| **SOR** (Start of Record) | 1 byte | メッセージ開始マーカー: `0x8E` | - |
| **Version** | 1 byte | プロトコルバージョン: `0x01` または `0x02` | - |
| **Length** | 2 bytes | メッセージ全体の長さ | Little-endian |
| **CRC** | 2 bytes | CRC16チェックサム | **Big-endian** |
| **Flags** | 2 bytes | フラグフィールド | Little-endian |
| **TOR** (Type of Record) | 2 bytes | レコードタイプ | Little-endian |
| **Body** | 可変 | メッセージボディ（TORに依存） | - |
| **EOR** (End of Record) | 1 byte | メッセージ終了マーカー: `0x8F` | - |

### バイトオーダーの注意点

⚠️ **重要**: フィールドごとにエンディアンが異なります

- **Big-endian**: CRCのみ
- **Little-endian**: Length, Flags, TOR
- メッセージ内の数値データ（RTC_TIME等）はlittle-endian

---

## CRC16検証

### CRC16アルゴリズム

AMB P3プロトコルは、以下のパラメータでCRC16-CCITTを使用します：

```python
POLYNOMIAL = 0x1021
INITIAL_VALUE = 0xFFFF
```

### CRC計算手順

1. **CRCフィールドをゼロに設定**
   ```python
   data_for_crc = bytearray(original_message)
   data_for_crc[4:6] = b'\x00\x00'  # CRC位置をゼロクリア
   ```

2. **全パケットでCRC計算**（SORとEORを含む）
   ```python
   crc_table = crc16.table()
   calculated_crc = crc16.calc(data_for_crc.hex(), crc_table)
   ```

3. **バイトスワップ**

   `crc16.calc()`関数は最後にバイトスワップを実行：
   ```python
   return (crc << 8 & 0xFFFF) | (crc >> 8)
   ```

4. **Big-endianで比較**
   ```python
   packet_crc = int.from_bytes(data[4:6], byteorder='big')
   if calculated_crc == packet_crc:
       # CRC valid
   ```

### 実装例

```python
def _check_crc(data):
    """CRCチェックの実装例"""
    if len(data) < 6:
        return None

    # パケットからCRCを抽出（big-endian）
    packet_crc = int.from_bytes(data[4:6], byteorder='big')

    # CRCフィールドをゼロにしたコピーを作成
    data_for_crc = bytearray(data)
    data_for_crc[4:6] = b'\x00\x00'

    # CRC計算
    crc_table = crc16.table()
    calculated_crc = crc16.calc(data_for_crc.hex(), crc_table)

    # 検証
    if calculated_crc != packet_crc:
        logger.error(f"CRC mismatch: expected {hex(packet_crc)}, got {hex(calculated_crc)}")
        return None

    return data
```

### CRC検証の例

```
メッセージ: 8e021f00f3890000020001022800070216000c01760601008104131804008f
          ^^^^^^^^  ^^^^
          Header    CRC = 0xf389

ゼロ化:   8e021f0000000000020001022800070216000c01760601008104131804008f
                  ^^^^
                  CRC = 0x0000

計算結果: 0xf389 ✅ 一致
```

---

## エスケープ処理

### エスケープが必要なバイト

以下のバイト値はメッセージの**最初と最後以外**で出現する場合、エスケープが必要です：

- `0x8D` (141)
- `0x8E` (142) - SOR
- `0x8F` (143) - EOR

### エスケープ方式

エスケープが必要なバイトは、`0x8D`プレフィックス + 元の値に`0x20`を加算した値に変換されます。

```
元のバイト → エスケープ後
0x8D → 0x8D 0xAD  (0x8D + 0x20 = 0xAD)
0x8E → 0x8D 0xAE  (0x8E + 0x20 = 0xAE)
0x8F → 0x8D 0xAF  (0x8F + 0x20 = 0xAF)
```

### デコード処理

```python
def _unescape(data):
    """エスケープされたデータをデコード"""
    # 最初と最後のバイト（SOR/EOR）を除外
    new_data = bytearray(data)[1:-1]
    escaped_data = bytearray()
    escape_next = False

    for byte in new_data:
        if escape_next:
            # エスケープされたバイトを復元（0x20を減算）
            escaped_data.append(byte - 32)
            escape_next = False
            continue
        if byte in [141, 142, 143]:  # 0x8D, 0x8E, 0x8F
            escape_next = True
        else:
            escaped_data.append(byte)

    # SORとEORを再挿入
    escaped_data.insert(0, 142)  # 0x8E
    escaped_data.append(143)     # 0x8F
    return bytes(escaped_data)
```

### エスケープの例

```
元のメッセージ:      8E 01 8D 03 8F
                      ^  ^  ^  ^  ^
                    SOR V  D  D EOR

エスケープ後:        8E 01 8D AD 03 8F
                      ^  ^  ^^^^^ ^  ^
                    SOR V  Esc.  D EOR
```

---

## 実装の詳細

### デコード処理フロー

```
受信データ
    ↓
1. CRC検証 (_check_crc)
    ↓
2. エスケープ解除 (_unescape)
    ↓
3. 長さチェック (_check_length)
    ↓
4. ヘッダー解析 (_get_header)
    ↓
5. ボディ解析 (_decode_body)
    ↓
デコード結果
```

### p3decode 関数

```python
def p3decode(data):
    """P3プロトコルメッセージをデコード

    Args:
        data: 生のバイナリデータ

    Returns:
        (header_dict, body_dict): デコード結果
        または (None, None): デコード失敗時
    """
    # 検証処理
    data = _validate(data)
    if data is None:
        return None, None

    # ヘッダー解析
    decoded_header = _get_header(data)

    # ボディ解析
    tor = decoded_header["TOR"]
    decoded_body = _decode_body(tor, data)

    return decoded_header, decoded_body
```

### 連結されたレコードの分割

デコーダーは時に複数のメッセージを1つのTCPパケットで送信します。これらは`0x8F8E`（EOR + SOR）パターンで識別されます：

```python
def split_records(self, data):
    """連結されたレコードを分割"""
    byte_array = bytearray(data)
    split_data = [bytearray()]

    for index, byte in enumerate(byte_array):
        if index != len(byte_array) - 1:
            if byte == 143 and byte_array[index + 1] == 142:  # 0x8F and 0x8E
                split_data[-1].append(byte)    # EORを追加
                split_data.append(bytearray()) # 新しいレコード開始
                continue
        split_data[-1].append(byte)

    return split_data
```

---

## トラブルシューティング

### よくある問題

#### 1. CRC検証失敗

**症状**: `CRC check failed` エラーログ

**原因**:
- データ転送中の破損
- エスケープ処理の誤り
- バイトオーダーの間違い

**解決策**:
```python
# CRCはbig-endianで読む
packet_crc = int.from_bytes(data[4:6], byteorder='big')  # ✅ 正しい
packet_crc = int.from_bytes(data[4:6], byteorder='little')  # ❌ 間違い
```

#### 2. エスケープ処理エラー

**症状**: デコード後のデータが不正

**原因**:
- SOR/EORをエスケープ処理している
- エスケープバイトの減算値が間違い

**解決策**:
```python
# 最初と最後を除外
new_data = bytearray(data)[1:-1]  # ✅ 正しい
new_data = bytearray(data)        # ❌ 間違い
```

#### 3. 連結レコードの処理漏れ

**症状**: 2番目以降のメッセージが処理されない

**原因**:
- `split_records()`を使用していない

**解決策**:
```python
for data in connection.read():
    # read()は既にsplit_records()を呼び出している
    decoded_header, decoded_body = p3decode(data)
```

### デバッグのヒント

#### 1. メッセージの16進ダンプ

```python
import codecs
hex_data = codecs.encode(data, 'hex').decode('ascii')
logger.debug(f"Raw message: {hex_data}")
```

#### 2. CRC計算の検証

```bash
# コマンドラインでCRC計算
python -m AmbP3.crc16 "8e021f0000000000020001022800070216000c01760601008104131804008f"
```

#### 3. フィールドごとの解析

```python
print(f"SOR: {hex(data[0])}")          # 0x8e
print(f"Version: {hex(data[1])}")      # 0x01 or 0x02
print(f"Length: {int.from_bytes(data[2:4], 'little')}")
print(f"CRC: {int.from_bytes(data[4:6], 'big')}")
print(f"Flags: {int.from_bytes(data[6:8], 'little')}")
print(f"TOR: {int.from_bytes(data[8:10], 'little')}")
```

---

## 参考資料

### プロトコル仕様

- `NOTES/CRC_NOTES` - CRC16実装の検証メモ
- `NOTES/CRC_CHECK` - 公式CRC計算アルゴリズム
- `AmbP3/records.py` - メッセージタイプ定義

### 実装ファイル

- `AmbP3/decoder.py` - プロトコルデコーダー実装
- `AmbP3/crc16.py` - CRC16計算モジュール
- `tests/integration/test_decoder_integration.py` - 統合テスト

### 外部リンク

- [CRC16-CCITT アルゴリズム](https://en.wikipedia.org/wiki/Cyclic_redundancy_check)
- [AMB Decoder 公式サイト](https://www.amb-it.com/)

---

## バージョン履歴

| バージョン | 日付 | 変更内容 |
|------------|------|----------|
| 1.0 | 2025-10-31 | 初版作成。CRC16検証実装の完全なドキュメント化 |

---

## 著者

- AMBp3client Development Team
- ドキュメント作成: Claude Code (2025-10-31)

---

## ライセンス

このドキュメントは、AMBp3clientプロジェクトと同じライセンス（Apache License 2.0）の下で提供されます。
