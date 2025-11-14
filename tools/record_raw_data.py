#!/usr/bin/env python
"""
AMB P3 Decoder Raw Data Recorder

このスクリプトは、AMB P3デコーダーから受信した生のバイナリデータを記録します。
公式のP3プロトコル仕様が公開されていないため、実際のデコーダーの動作を
解析・記録するために使用します。

記録されるデータ:
- 受信した生のバイナリデータ（hex形式）
- タイムスタンプ（受信時刻）
- デコード結果（オプション）

出力形式:
JSONL（JSON Lines）形式で、1行に1レコードを記録します。

使用例:
    # 設定ファイルを指定して実行
    ./tools/record_raw_data.py -f local_conf.yaml

    # 出力ファイルを指定
    ./tools/record_raw_data.py -f local_conf.yaml -o captured_data.jsonl

    # デコード結果を含めずに記録（生データのみ）
    ./tools/record_raw_data.py -f local_conf.yaml --no-decode
"""

import json
import sys
import os
import logging
from datetime import datetime
from time import sleep
import argparse

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from AmbP3.config import get_args, Config
from AmbP3.decoder import Connection, DecoderConnectionError, DecoderReadError
from AmbP3.decoder import p3decode

# ロギング設定
logger = logging.getLogger("raw_data_recorder")


def setup_logging(verbose=False):
    """ロギングを設定する"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_arguments():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="AMB P3デコーダーの生データを記録するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本的な使い方
  %(prog)s -f local_conf.yaml

  # 出力ファイルを指定
  %(prog)s -f local_conf.yaml -o captured_data.jsonl

  # デコード結果を含めない（生データのみ）
  %(prog)s -f local_conf.yaml --no-decode

  # デバッグモード
  %(prog)s -f local_conf.yaml -v
        """
    )

    parser.add_argument(
        '-f', '--config',
        required=True,
        help='設定ファイルのパス（例: local_conf.yaml）'
    )

    parser.add_argument(
        '-o', '--output',
        help='出力ファイルのパス（デフォルト: raw_data_YYYYMMDD_HHMMSS.jsonl）'
    )

    parser.add_argument(
        '--no-decode',
        action='store_true',
        help='デコード結果を記録しない（生データのみ記録）'
    )

    parser.add_argument(
        '--skip-crc-check',
        action='store_true',
        default=True,
        help='CRC検証をスキップ（デフォルト: True）'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='詳細なログを出力'
    )

    return parser.parse_args()


def connect_to_decoder(ip, port, max_retries=5, retry_interval=5.0):
    """デコーダーに接続する（リトライ機能付き）

    Args:
        ip: デコーダーのIPアドレス
        port: デコーダーのポート番号
        max_retries: 最大リトライ回数
        retry_interval: リトライ間隔（秒）

    Returns:
        Connection: 接続オブジェクト

    Raises:
        DecoderConnectionError: 接続に失敗した場合
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"デコーダーに接続中 {ip}:{port} (試行 {retry_count + 1}/{max_retries})")
            connection = Connection(ip, port)
            connection.connect()
            logger.info(f"デコーダーに接続しました: {ip}:{port}")
            return connection
        except DecoderConnectionError as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"接続失敗: {e}. {retry_interval}秒後に再試行...")
                sleep(retry_interval)
            else:
                logger.error(f"{max_retries}回の試行後、デコーダーへの接続に失敗しました")
                raise

    raise DecoderConnectionError(f"{max_retries}回の試行後、{ip}:{port}への接続に失敗")


def record_raw_data(connection, output_file, include_decode=True, skip_crc_check=True):
    """デコーダーから生データを記録する

    Args:
        connection: デコーダー接続オブジェクト
        output_file: 出力ファイルオブジェクト
        include_decode: デコード結果を含めるか
        skip_crc_check: CRC検証をスキップするか
    """
    record_count = 0
    error_count = 0

    logger.info("データ記録を開始します（Ctrl+Cで停止）")
    logger.info(f"出力ファイル: {output_file.name}")
    logger.info(f"デコード結果の記録: {'有効' if include_decode else '無効'}")
    logger.info(f"CRC検証: {'無効' if skip_crc_check else '有効'}")

    try:
        while True:
            try:
                # デコーダーからデータを読み取る
                data_list = connection.read()

                for data in data_list:
                    record_count += 1

                    # 受信時刻を記録
                    timestamp = datetime.now().isoformat()

                    # 生データをhex文字列に変換
                    raw_hex = data.hex()

                    # 記録するデータ
                    record = {
                        "timestamp": timestamp,
                        "record_number": record_count,
                        "raw_data_hex": raw_hex,
                        "raw_data_length": len(data),
                    }

                    # デコード結果を含める場合
                    if include_decode:
                        try:
                            decoded_header, decoded_body = p3decode(data, skip_crc_check=skip_crc_check)

                            if decoded_header is not None and decoded_body is not None:
                                # バイナリデータをhex文字列に変換
                                header_hex = {}
                                for key, value in decoded_header.items():
                                    if isinstance(value, bytes):
                                        header_hex[key] = value.hex()
                                    else:
                                        header_hex[key] = value

                                record["decoded"] = {
                                    "header": header_hex,
                                    "body": decoded_body,
                                    "decode_success": True
                                }
                            else:
                                record["decoded"] = {
                                    "decode_success": False,
                                    "error": "デコード失敗（データがNone）"
                                }
                                error_count += 1
                        except Exception as e:
                            record["decoded"] = {
                                "decode_success": False,
                                "error": str(e)
                            }
                            error_count += 1
                            logger.warning(f"デコードエラー (レコード {record_count}): {e}")

                    # JSONLフォーマットで1行に1レコード書き込み
                    json_line = json.dumps(record, ensure_ascii=False)
                    output_file.write(json_line + '\n')
                    output_file.flush()  # 即座にディスクに書き込む

                    if record_count % 10 == 0:
                        logger.info(f"記録済みレコード: {record_count}, エラー: {error_count}")

                # 短い間隔でポーリング
                sleep(0.2)

            except DecoderReadError as e:
                logger.error(f"デコーダー読み取りエラー: {e}")
                logger.info("再接続が必要な場合があります")
                raise
            except Exception as e:
                logger.error(f"予期しないエラー: {e}")
                error_count += 1

    except KeyboardInterrupt:
        logger.info("\n\nCtrl+Cが押されました。記録を停止します...")
    finally:
        logger.info(f"記録完了: 合計 {record_count} レコード, エラー {error_count} 件")
        logger.info(f"出力ファイル: {output_file.name}")


def main():
    """メイン関数"""
    # コマンドライン引数を解析
    args = parse_arguments()

    # ロギングを設定
    setup_logging(args.verbose)

    logger.info("=" * 60)
    logger.info("AMB P3 Decoder Raw Data Recorder")
    logger.info("=" * 60)

    # 設定ファイルを読み込む
    try:
        # sys.argvを一時的に変更して設定ファイルを読み込む
        original_argv = sys.argv
        sys.argv = ['record_raw_data.py', '-f', args.config]
        config = get_args()
        sys.argv = original_argv

        logger.info(f"設定ファイル読み込み完了: {args.config}")
        logger.info(f"デコーダー: {config.ip}:{config.port}")
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗: {e}")
        sys.exit(1)

    # 出力ファイル名を決定
    if args.output:
        output_filename = args.output
    else:
        # デフォルト: raw_data_YYYYMMDD_HHMMSS.jsonl
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"raw_data_{timestamp}.jsonl"

    # デコーダーに接続
    try:
        connection = connect_to_decoder(config.ip, config.port)
    except DecoderConnectionError as e:
        logger.error(f"デコーダーへの接続に失敗しました: {e}")
        sys.exit(1)

    # 生データを記録
    try:
        with open(output_filename, 'w', encoding='utf-8') as output_file:
            record_raw_data(
                connection,
                output_file,
                include_decode=not args.no_decode,
                skip_crc_check=args.skip_crc_check
            )
    except Exception as e:
        logger.error(f"データ記録中にエラーが発生しました: {e}")
        sys.exit(1)
    finally:
        try:
            connection.close()
            logger.info("デコーダー接続を切断しました")
        except Exception:
            pass

    logger.info("プログラムを終了します")


if __name__ == "__main__":
    main()
