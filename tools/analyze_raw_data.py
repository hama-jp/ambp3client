#!/usr/bin/env python
"""
AMB P3 Raw Data Analyzer

record_raw_data.pyで記録した生データファイル（JSONL形式）を解析するツールです。

使用例:
    # すべてのレコードを表示
    ./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl

    # デコード失敗したレコードのみ表示
    ./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --failed-only

    # 特定のTORタイプのみ表示
    ./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --tor PASSING

    # 統計情報を表示
    ./tools/analyze_raw_data.py raw_data_20251114_123456.jsonl --stats
"""

import json
import sys
import argparse
from collections import Counter
from datetime import datetime


def parse_arguments():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="AMB P3生データファイル（JSONL形式）を解析するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'input_file',
        help='解析する生データファイル（JSONL形式）'
    )

    parser.add_argument(
        '--failed-only',
        action='store_true',
        help='デコード失敗したレコードのみ表示'
    )

    parser.add_argument(
        '--tor',
        help='特定のTOR（Type of Record）のレコードのみ表示（例: PASSING, GET_TIME）'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='統計情報を表示'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='表示するレコード数の上限'
    )

    return parser.parse_args()


def load_records(filename):
    """JSONLファイルからレコードを読み込む"""
    records = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"警告: 行 {line_num} のJSONパースに失敗: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {filename}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: ファイル読み込み中にエラーが発生: {e}", file=sys.stderr)
        sys.exit(1)

    return records


def display_record(record, index=None):
    """レコードを表示する"""
    if index is not None:
        print(f"\n{'='*60}")
        print(f"レコード #{index}")
        print(f"{'='*60}")
    else:
        print(f"\n{'-'*60}")

    print(f"タイムスタンプ: {record['timestamp']}")
    print(f"レコード番号: {record['record_number']}")
    print(f"データ長: {record['raw_data_length']} バイト")
    print(f"生データ (hex): {record['raw_data_hex']}")

    if 'decoded' in record:
        decoded = record['decoded']
        if decoded.get('decode_success'):
            print(f"\nデコード: 成功")

            if 'header' in decoded:
                print(f"\nヘッダー:")
                for key, value in decoded['header'].items():
                    print(f"  {key}: {value}")

            if 'body' in decoded and 'RESULT' in decoded['body']:
                result = decoded['body']['RESULT']
                print(f"\nボディ:")
                for key, value in result.items():
                    print(f"  {key}: {value}")
        else:
            print(f"\nデコード: 失敗")
            if 'error' in decoded:
                print(f"エラー: {decoded['error']}")


def show_statistics(records):
    """統計情報を表示する"""
    print(f"\n{'='*60}")
    print("統計情報")
    print(f"{'='*60}")

    total_records = len(records)
    print(f"\n総レコード数: {total_records}")

    if total_records == 0:
        return

    # デコード成功/失敗の統計
    decode_success_count = sum(
        1 for r in records
        if 'decoded' in r and r['decoded'].get('decode_success')
    )
    decode_failed_count = sum(
        1 for r in records
        if 'decoded' in r and not r['decoded'].get('decode_success')
    )
    no_decode_count = total_records - decode_success_count - decode_failed_count

    print(f"\nデコード統計:")
    print(f"  成功: {decode_success_count} ({decode_success_count/total_records*100:.1f}%)")
    print(f"  失敗: {decode_failed_count} ({decode_failed_count/total_records*100:.1f}%)")
    if no_decode_count > 0:
        print(f"  デコードなし: {no_decode_count} ({no_decode_count/total_records*100:.1f}%)")

    # TOR（Type of Record）の統計
    tor_types = []
    for r in records:
        if 'decoded' in r and r['decoded'].get('decode_success'):
            if 'body' in r['decoded'] and 'RESULT' in r['decoded']['body']:
                tor = r['decoded']['body']['RESULT'].get('TOR')
                if tor:
                    tor_types.append(tor)

    if tor_types:
        tor_counter = Counter(tor_types)
        print(f"\nTOR（レコードタイプ）分布:")
        for tor, count in tor_counter.most_common():
            print(f"  {tor}: {count} ({count/len(tor_types)*100:.1f}%)")

    # データサイズの統計
    data_lengths = [r['raw_data_length'] for r in records]
    print(f"\nデータサイズ:")
    print(f"  最小: {min(data_lengths)} バイト")
    print(f"  最大: {max(data_lengths)} バイト")
    print(f"  平均: {sum(data_lengths)/len(data_lengths):.1f} バイト")

    # 時系列情報
    try:
        timestamps = [
            datetime.fromisoformat(r['timestamp'])
            for r in records
            if 'timestamp' in r
        ]
        if len(timestamps) >= 2:
            duration = (timestamps[-1] - timestamps[0]).total_seconds()
            print(f"\n記録時間:")
            print(f"  開始: {timestamps[0]}")
            print(f"  終了: {timestamps[-1]}")
            print(f"  期間: {duration:.1f} 秒")
            print(f"  平均レート: {total_records/duration:.2f} レコード/秒")
    except Exception as e:
        print(f"\n時系列情報の解析に失敗: {e}", file=sys.stderr)


def main():
    """メイン関数"""
    args = parse_arguments()

    # レコードを読み込む
    print(f"ファイル読み込み中: {args.input_file}")
    records = load_records(args.input_file)
    print(f"読み込み完了: {len(records)} レコード")

    # 統計情報のみ表示
    if args.stats:
        show_statistics(records)
        return

    # フィルタリング
    filtered_records = records

    if args.failed_only:
        filtered_records = [
            r for r in filtered_records
            if 'decoded' in r and not r['decoded'].get('decode_success')
        ]
        print(f"デコード失敗レコード: {len(filtered_records)} 件")

    if args.tor:
        filtered_records = [
            r for r in filtered_records
            if 'decoded' in r
            and r['decoded'].get('decode_success')
            and 'body' in r['decoded']
            and 'RESULT' in r['decoded']['body']
            and r['decoded']['body']['RESULT'].get('TOR') == args.tor
        ]
        print(f"TOR '{args.tor}' のレコード: {len(filtered_records)} 件")

    # 上限を適用
    if args.limit:
        filtered_records = filtered_records[:args.limit]

    # レコードを表示
    for i, record in enumerate(filtered_records, 1):
        display_record(record, i)

    # 表示したレコード数
    print(f"\n{'='*60}")
    print(f"表示したレコード: {len(filtered_records)} / {len(records)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
