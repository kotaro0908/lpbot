#!/usr/bin/env python3
"""
LP BOT監視システム - JSONログインポーター
JSONログファイルからSQLiteデータベースへのデータ取り込み
"""

import json
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

# データベースパス
DB_PATH = Path(__file__).parent.parent / "lpbot.db"
LOGS_DIR = Path(__file__).parent.parent.parent  # /root/lpbot/


class JSONLogImporter:
    """JSONログをデータベースにインポートするクラス"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def connect(self):
        """データベース接続"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # 外部キー制約を有効化
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self):
        """データベース切断"""
        if self.conn:
            self.conn.close()

    def get_log_files(self, days_back=7) -> List[Path]:
        """対象のログファイルを取得"""
        log_files = []

        # 今日から過去N日分のファイルを確認
        for i in range(days_back):
            date = datetime.now() - timedelta(days=i)
            filename = f"logs_{date.strftime('%Y-%m-%d')}.json"
            filepath = LOGS_DIR / filename

            if filepath.exists():
                log_files.append(filepath)

        # archiveフォルダも確認
        archive_dir = LOGS_DIR / "archive"
        if archive_dir.exists():
            for file in archive_dir.glob("logs_*.json"):
                log_files.append(file)

        return sorted(log_files)

    def parse_log_line(self, line: str) -> Dict[str, Any]:
        """ログ行をパース"""
        try:
            # 空行やコメントをスキップ
            line = line.strip()
            if not line or line.startswith('#'):
                return None

            return json.loads(line)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSONパースエラー: {e}")
            return None

    def check_duplicate(self, table: str, timestamp: str, unique_fields: Dict) -> bool:
        """重複チェック"""
        # タイムスタンプを秒単位に丸めて比較（ミリ秒の違いを無視）
        timestamp_seconds = timestamp.split('.')[0] if '.' in timestamp else timestamp

        # タイムスタンプベースの重複チェック
        query = f"SELECT 1 FROM {table} WHERE datetime(timestamp, 'start of second') = datetime(?, 'start of second')"
        params = [timestamp_seconds]

        # 追加の一意性フィールド
        for field, value in unique_fields.items():
            query += f" AND {field} = ?"
            params.append(value)

        cursor = self.conn.execute(query + " LIMIT 1", params)
        return cursor.fetchone() is not None

    def import_rebalance(self, data: Dict):
        """リバランスイベントのインポート"""
        try:
            # 重複チェック
            unique_fields = {
                'reason': data.get('reason'),
                'old_nft_id': data.get('old_nft_id'),
                'new_nft_id': data.get('new_nft_id')
            }

            if self.check_duplicate('rebalance_history', data['timestamp'], unique_fields):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO rebalance_history (timestamp, reason, old_nft_id, new_nft_id,
                                                             old_tick_lower, old_tick_upper, new_tick_lower,
                                                             new_tick_upper,
                                                             price_at_rebalance, estimated_amount, actual_amount,
                                                             swap_executed, tx_hash, success, error_message)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('reason', 'unknown'),
                                  data.get('old_nft_id'),
                                  data.get('new_nft_id'),
                                  data.get('old_tick_lower'),
                                  data.get('old_tick_upper'),
                                  data.get('new_tick_lower'),
                                  data.get('new_tick_upper'),
                                  data.get('price_at_rebalance'),
                                  data.get('estimated_amount'),
                                  data.get('actual_amount'),
                                  1 if data.get('swap_executed', False) else 0,
                                  data.get('tx_hash'),
                                  1 if data.get('success', True) else 0,
                                  data.get('error_message')
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ リバランスインポートエラー: {e}")
            self.error_count += 1

    def import_swap(self, data: Dict):
        """SWAPイベントのインポート"""
        try:
            # 重複チェック
            if self.check_duplicate('swap_history', data['timestamp'], {}):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO swap_history (timestamp, from_token, to_token, amount,
                                                        swap_direction, tx_hash, success, error_message)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('from_token'),
                                  data.get('to_token'),
                                  data.get('amount'),
                                  data.get('swap_direction'),
                                  data.get('tx_hash'),
                                  1 if data.get('success', True) else 0,
                                  data.get('error_message')
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ SWAPインポートエラー: {e}")
            self.error_count += 1

    def import_fund_change(self, data: Dict):
        """資金変動イベントのインポート"""
        try:
            # 重複チェック
            if self.check_duplicate('fund_changes', data['timestamp'], {}):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO fund_changes (timestamp, change_type, amount_usd,
                                                        eth_balance, weth_balance, usdc_balance,
                                                        total_value_usd, trigger_action)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('change_type'),
                                  data.get('amount_usd'),
                                  data.get('eth_balance'),
                                  data.get('weth_balance'),
                                  data.get('usdc_balance'),
                                  data.get('total_value_usd'),
                                  data.get('trigger_action')
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ 資金変動インポートエラー: {e}")
            self.error_count += 1

    def import_gas_retry(self, data: Dict):
        """ガスリトライイベントのインポート"""
        try:
            # 重複チェック
            unique_fields = {
                'function_name': data.get('function_name'),
                'attempt': data.get('attempt')
            }

            if self.check_duplicate('gas_retry_history', data['timestamp'], unique_fields):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO gas_retry_history (timestamp, function_name, attempt,
                                                             gas_limit, gas_multiplier, success)
                              VALUES (?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('function_name'),
                                  data.get('attempt'),
                                  data.get('gas_limit'),
                                  data.get('gas_multiplier'),
                                  1 if data.get('success', False) else 0
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ ガスリトライインポートエラー: {e}")
            self.error_count += 1

    def import_lp_creation(self, data: Dict):
        """LP作成イベントのインポート"""
        try:
            # 重複チェック
            unique_fields = {'tx_hash': data.get('tx_hash')} if data.get('tx_hash') else {}

            if self.check_duplicate('lp_creation_history', data['timestamp'], unique_fields):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO lp_creation_history (timestamp, tx_hash, gas_used, events,
                                                               tick_lower, tick_upper, amount_weth, amount_usdc,
                                                               success, error_message)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('tx_hash'),
                                  data.get('gas_used'),
                                  data.get('events'),
                                  data.get('tick_lower'),
                                  data.get('tick_upper'),
                                  data.get('amount_weth'),
                                  data.get('amount_usdc'),
                                  1 if data.get('success', True) else 0,
                                  data.get('error', data.get('error_message'))
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ LP作成インポートエラー: {e}")
            self.error_count += 1

    def import_system_log(self, data: Dict):
        """システムログのインポート"""
        try:
            # 重複チェック
            if self.check_duplicate('system_logs', data['timestamp'], {}):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO system_logs (timestamp, log_level, function_name,
                                                       message, execution_time_ms, error_details)
                              VALUES (?, ?, ?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('log_level', 'INFO'),
                                  data.get('function_name'),
                                  data.get('message'),
                                  data.get('execution_time_ms'),
                                  data.get('error_details')
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ システムログインポートエラー: {e}")
            self.error_count += 1

    def import_monitoring_cycle(self, data: Dict):
        """監視サイクルイベントのインポート"""
        try:
            # 重複チェック
            unique_fields = {'cycle': data.get('cycle')}

            if self.check_duplicate('monitoring_cycles', data['timestamp'], unique_fields):
                self.skipped_count += 1
                return

            # データ挿入
            self.conn.execute("""
                              INSERT INTO monitoring_cycles (timestamp, cycle, tracked_nfts, status)
                              VALUES (?, ?, ?, ?)
                              """, (
                                  data['timestamp'],
                                  data.get('cycle'),
                                  json.dumps(data.get('tracked_nfts', [])),
                                  data.get('status', 'started')
                              ))

            self.imported_count += 1

        except Exception as e:
            print(f"❌ 監視サイクルインポートエラー: {e}")
            self.error_count += 1

    def import_log_entry(self, entry: Dict):
        """ログエントリのインポート（タイプ別振り分け）"""
        if not entry or 'type' not in entry:
            return

        log_type = entry['type']

        # タイプ別の処理
        if log_type == 'rebalance':
            self.import_rebalance(entry)
        elif log_type == 'swap':
            self.import_swap(entry)
        elif log_type == 'fund_change':
            self.import_fund_change(entry)
        elif log_type == 'gas_retry':
            self.import_gas_retry(entry)
        elif log_type == 'lp_creation':
            self.import_lp_creation(entry)
        elif log_type == 'system':
            self.import_system_log(entry)
        elif log_type == 'monitoring_cycle':
            self.import_monitoring_cycle(entry)
        else:
            # その他のタイプはシステムログとして記録
            entry['log_level'] = 'INFO'
            entry['message'] = f"Unknown log type: {log_type}"
            self.import_system_log(entry)

    def import_file(self, filepath: Path):
        """ファイル単位でのインポート"""
        print(f"\n📄 ファイル処理: {filepath.name}")

        file_imported = 0
        file_skipped = 0
        file_errors = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    entry = self.parse_log_line(line)
                    if entry:
                        before_imported = self.imported_count
                        before_skipped = self.skipped_count
                        before_errors = self.error_count

                        self.import_log_entry(entry)

                        # ファイル単位の統計更新
                        if self.imported_count > before_imported:
                            file_imported += 1
                        elif self.skipped_count > before_skipped:
                            file_skipped += 1
                        elif self.error_count > before_errors:
                            file_errors += 1

            print(f"   ✅ インポート: {file_imported}件")
            print(f"   ⏭️  スキップ: {file_skipped}件（重複）")
            if file_errors > 0:
                print(f"   ❌ エラー: {file_errors}件")

        except Exception as e:
            print(f"   ❌ ファイル読み込みエラー: {e}")

    def update_metadata(self):
        """メタデータ更新"""
        self.conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_import_at', ?, CURRENT_TIMESTAMP)
        """, (datetime.now().isoformat(),))

        self.conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('total_imported', ?, CURRENT_TIMESTAMP)
        """, (str(self.imported_count),))

    def update_daily_performance(self):
        """日次パフォーマンスの集計更新"""
        print("\n📊 日次パフォーマンス集計中...")

        # 各日付のリバランス回数を集計
        self.conn.execute("""
            INSERT OR REPLACE INTO daily_performance (
                date, rebalance_count, error_count, success_rate
            )
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as rebalance_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
                AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM rebalance_history
            GROUP BY DATE(timestamp)
        """)

        # SWAP回数を更新
        self.conn.execute("""
                          UPDATE daily_performance
                          SET swap_count = (SELECT COUNT(*)
                                            FROM swap_history
                                            WHERE DATE (swap_history.timestamp) = daily_performance.date
                              )
                          """)

        print("   ✅ 日次パフォーマンス更新完了")

    def run_import(self, days_back=7):
        """インポート実行"""
        print(f"\n🚀 JSONログインポート開始")
        print(f"📍 データベース: {self.db_path}")
        print(f"📅 対象期間: 過去{days_back}日間")

        try:
            # データベース接続
            self.connect()

            # 対象ファイル取得
            log_files = self.get_log_files(days_back)
            print(f"\n📁 対象ファイル: {len(log_files)}個")

            if not log_files:
                print("⚠️  インポート対象のログファイルが見つかりません")
                return

            # 各ファイルをインポート
            for filepath in log_files:
                self.import_file(filepath)
                # コミット（ファイル単位）
                self.conn.commit()

            # 日次パフォーマンス更新
            self.update_daily_performance()

            # メタデータ更新
            self.update_metadata()

            # 最終コミット
            self.conn.commit()

            # 結果表示
            print(f"\n📊 インポート結果:")
            print(f"   ✅ インポート: {self.imported_count}件")
            print(f"   ⏭️  スキップ: {self.skipped_count}件（重複）")
            if self.error_count > 0:
                print(f"   ❌ エラー: {self.error_count}件")

            # 統計情報表示
            self.show_statistics()

            print("\n✅ インポート完了!")

        except Exception as e:
            print(f"\n❌ インポートエラー: {e}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self.close()

    def show_statistics(self):
        """データベース統計情報の表示"""
        print("\n📈 データベース統計:")

        # 各テーブルの件数
        tables = [
            'rebalance_history',
            'swap_history',
            'fund_changes',
            'gas_retry_history',
            'lp_creation_history',
            'system_logs',
            'monitoring_cycles'
        ]

        for table in tables:
            cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count}件")

        # 最新のリバランス
        cursor = self.conn.execute("""
                                   SELECT timestamp, old_nft_id, new_nft_id
                                   FROM rebalance_history
                                   ORDER BY timestamp DESC
                                       LIMIT 1
                                   """)
        latest = cursor.fetchone()
        if latest:
            print(f"\n   最新リバランス: {latest['timestamp']}")
            print(f"   NFT: {latest['old_nft_id']} → {latest['new_nft_id']}")


def main():
    """メイン実行関数"""
    import argparse

    parser = argparse.ArgumentParser(description='JSONログをデータベースにインポート')
    parser.add_argument('--days', type=int, default=7, help='過去何日分をインポートするか（デフォルト: 7）')
    parser.add_argument('--all', action='store_true', help='全ての利用可能なログをインポート')

    args = parser.parse_args()

    # インポーター実行
    importer = JSONLogImporter()

    if args.all:
        importer.run_import(days_back=365)  # 実質的に全て
    else:
        importer.run_import(days_back=args.days)


if __name__ == "__main__":
    main()