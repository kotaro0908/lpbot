#!/usr/bin/env python3
"""
LP BOT監視システム - データベース初期化スクリプト
SQLiteデータベースの作成とテーブル定義
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# データベースパス
DB_PATH = Path(__file__).parent / "lpbot.db"
SCHEMA_VERSION = "1.0.0"


class DatabaseInitializer:
    """データベース初期化クラス"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None

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

    def create_tables(self):
        """全テーブルの作成"""
        print("📊 データベーステーブルを作成中...")

        # リバランス履歴テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS rebalance_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              reason
                              TEXT
                              NOT
                              NULL,
                              old_nft_id
                              INTEGER,
                              new_nft_id
                              INTEGER,
                              old_tick_lower
                              INTEGER,
                              old_tick_upper
                              INTEGER,
                              new_tick_lower
                              INTEGER,
                              new_tick_upper
                              INTEGER,
                              price_at_rebalance
                              REAL,
                              estimated_amount
                              REAL,
                              actual_amount
                              REAL,
                              swap_executed
                              BOOLEAN
                              DEFAULT
                              0,
                              tx_hash
                              TEXT,
                              gas_used
                              INTEGER,
                              gas_price
                              REAL,
                              success
                              BOOLEAN
                              DEFAULT
                              1,
                              error_message
                              TEXT,
                              duration_seconds
                              INTEGER,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # 資金変動履歴テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS fund_changes
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              change_type
                              TEXT
                              NOT
                              NULL,
                              amount_usd
                              REAL
                              NOT
                              NULL,
                              eth_balance
                              REAL,
                              weth_balance
                              REAL,
                              usdc_balance
                              REAL,
                              total_value_usd
                              REAL,
                              trigger_action
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # SWAP履歴テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS swap_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              from_token
                              TEXT
                              NOT
                              NULL,
                              to_token
                              TEXT
                              NOT
                              NULL,
                              amount
                              REAL
                              NOT
                              NULL,
                              swap_direction
                              TEXT
                              NOT
                              NULL,
                              tx_hash
                              TEXT,
                              success
                              BOOLEAN
                              DEFAULT
                              1,
                              error_message
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # ガスリトライ履歴テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS gas_retry_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              function_name
                              TEXT
                              NOT
                              NULL,
                              attempt
                              INTEGER
                              NOT
                              NULL,
                              gas_limit
                              INTEGER
                              NOT
                              NULL,
                              gas_multiplier
                              REAL
                              NOT
                              NULL,
                              success
                              BOOLEAN
                              DEFAULT
                              0,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # LP作成履歴テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS lp_creation_history
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              tx_hash
                              TEXT,
                              gas_used
                              INTEGER,
                              events
                              INTEGER,
                              tick_lower
                              INTEGER,
                              tick_upper
                              INTEGER,
                              amount_weth
                              REAL,
                              amount_usdc
                              REAL,
                              success
                              BOOLEAN
                              DEFAULT
                              1,
                              error_message
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # システムログテーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS system_logs
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              log_level
                              TEXT
                              NOT
                              NULL,
                              function_name
                              TEXT,
                              message
                              TEXT
                              NOT
                              NULL,
                              execution_time_ms
                              INTEGER,
                              error_details
                              TEXT,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # 監視サイクルテーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS monitoring_cycles
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              timestamp
                              DATETIME
                              NOT
                              NULL,
                              cycle
                              INTEGER
                              NOT
                              NULL,
                              tracked_nfts
                              TEXT,
                              status
                              TEXT
                              NOT
                              NULL,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # パフォーマンス指標（日次集計）テーブル
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS daily_performance
                          (
                              date
                              DATE
                              PRIMARY
                              KEY,
                              total_value_usd
                              REAL,
                              fee_earned_usd
                              REAL,
                              impermanent_loss_usd
                              REAL,
                              gas_spent_usd
                              REAL,
                              net_profit_usd
                              REAL,
                              apr_percent
                              REAL,
                              rebalance_count
                              INTEGER
                              DEFAULT
                              0,
                              swap_count
                              INTEGER
                              DEFAULT
                              0,
                              error_count
                              INTEGER
                              DEFAULT
                              0,
                              success_rate
                              REAL,
                              in_range_percent
                              REAL,
                              created_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP,
                              updated_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        # メタデータテーブル（スキーマバージョン管理）
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS metadata
                          (
                              key
                              TEXT
                              PRIMARY
                              KEY,
                              value
                              TEXT
                              NOT
                              NULL,
                              updated_at
                              DATETIME
                              DEFAULT
                              CURRENT_TIMESTAMP
                          )
                          """)

        self.conn.commit()
        print("✅ テーブル作成完了")

    def create_indexes(self):
        """インデックスの作成"""
        print("🔍 インデックスを作成中...")

        # リバランス履歴のインデックス
        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_rebalance_timestamp
                              ON rebalance_history(timestamp DESC)
                          """)

        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_rebalance_nft
                              ON rebalance_history(old_nft_id, new_nft_id)
                          """)

        # 資金変動のインデックス
        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_fund_changes_timestamp
                              ON fund_changes(timestamp DESC)
                          """)

        # SWAP履歴のインデックス
        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_swap_timestamp
                              ON swap_history(timestamp DESC)
                          """)

        # システムログのインデックス
        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp
                              ON system_logs(timestamp DESC)
                          """)

        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_system_logs_level
                              ON system_logs(log_level)
                          """)

        # 監視サイクルのインデックス
        self.conn.execute("""
                          CREATE INDEX IF NOT EXISTS idx_monitoring_cycles_timestamp
                              ON monitoring_cycles(timestamp DESC)
                          """)

        self.conn.commit()
        print("✅ インデックス作成完了")

    def insert_metadata(self):
        """メタデータの挿入"""
        print("📋 メタデータを設定中...")

        # スキーマバージョン
        self.conn.execute("""
        INSERT OR REPLACE INTO metadata (key, value) 
        VALUES ('schema_version', ?)
        """, (SCHEMA_VERSION,))

        # 初期化日時
        self.conn.execute("""
        INSERT OR REPLACE INTO metadata (key, value) 
        VALUES ('initialized_at', ?)
        """, (datetime.now().isoformat(),))

        # 最終更新日時
        self.conn.execute("""
        INSERT OR REPLACE INTO metadata (key, value) 
        VALUES ('last_import_at', ?)
        """, ('NULL',))

        self.conn.commit()
        print("✅ メタデータ設定完了")

    def create_views(self):
        """便利なビューの作成"""
        print("👁️ ビューを作成中...")

        # 最新のリバランス状況ビュー
        self.conn.execute("""
                          CREATE VIEW IF NOT EXISTS v_latest_rebalance AS
                          SELECT r.*,
                                 CASE
                                     WHEN r.success = 1 THEN 'SUCCESS'
                                     ELSE 'FAILED'
                                     END                                as status_text,
                                 (r.actual_amount - r.estimated_amount) as amount_diff
                          FROM rebalance_history r
                          ORDER BY r.timestamp DESC LIMIT 10
                          """)

        # 日次サマリービュー
        self.conn.execute("""
                          CREATE VIEW IF NOT EXISTS v_daily_summary AS
                          SELECT
                              DATE (timestamp) as date, COUNT (*) as rebalance_count, SUM (CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count, AVG (CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate, COUNT (DISTINCT old_nft_id || '-' || new_nft_id) as unique_transitions
                          FROM rebalance_history
                          GROUP BY DATE (timestamp)
                          ORDER BY date DESC
                          """)

        # アクティブNFTビュー
        self.conn.execute("""
                          CREATE VIEW IF NOT EXISTS v_active_nfts AS
                          SELECT new_nft_id     as nft_id,
                                 MAX(timestamp) as last_seen,
                                 new_tick_lower as tick_lower,
                                 new_tick_upper as tick_upper
                          FROM rebalance_history
                          WHERE success = 1
                            AND new_nft_id IS NOT NULL
                          GROUP BY new_nft_id
                          ORDER BY MAX(timestamp) DESC
                          """)

        self.conn.commit()
        print("✅ ビュー作成完了")

    def initialize(self):
        """データベースの完全初期化"""
        print(f"\n🚀 LP BOT監視データベース初期化開始")
        print(f"📍 データベースパス: {self.db_path}")

        try:
            # データベース接続
            self.connect()

            # 各種作成処理
            self.create_tables()
            self.create_indexes()
            self.create_views()
            self.insert_metadata()

            # 統計情報表示
            self.show_statistics()

            print("\n✅ データベース初期化完了!")

        except Exception as e:
            print(f"\n❌ エラー発生: {e}")
            raise
        finally:
            self.close()

    def show_statistics(self):
        """データベース統計情報の表示"""
        print("\n📊 データベース統計:")

        # テーブル一覧
        cursor = self.conn.execute("""
                                   SELECT name
                                   FROM sqlite_master
                                   WHERE type = 'table'
                                     AND name NOT LIKE 'sqlite_%'
                                   ORDER BY name
                                   """)

        tables = cursor.fetchall()
        print(f"   テーブル数: {len(tables)}")

        for table in tables:
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table['name']}").fetchone()[0]
            print(f"   - {table['name']}: {count} 件")

        # インデックス数
        cursor = self.conn.execute("""
                                   SELECT COUNT(*)
                                   FROM sqlite_master
                                   WHERE type = 'index'
                                     AND name NOT LIKE 'sqlite_%'
                                   """)
        index_count = cursor.fetchone()[0]
        print(f"   インデックス数: {index_count}")

        # ビュー数
        cursor = self.conn.execute("""
                                   SELECT COUNT(*)
                                   FROM sqlite_master
                                   WHERE type = 'view'
                                   """)
        view_count = cursor.fetchone()[0]
        print(f"   ビュー数: {view_count}")

        # データベースサイズ
        db_size = os.path.getsize(self.db_path) / 1024  # KB
        print(f"   データベースサイズ: {db_size:.2f} KB")


def main():
    """メイン実行関数"""
    # 既存のデータベースがある場合の確認
    if DB_PATH.exists():
        response = input(f"\n⚠️  既存のデータベースが見つかりました。\n上書きしますか？ (y/N): ")
        if response.lower() != 'y':
            print("❌ 初期化をキャンセルしました")
            return
        else:
            # バックアップ作成
            backup_path = DB_PATH.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
            os.rename(DB_PATH, backup_path)
            print(f"📦 バックアップ作成: {backup_path}")

    # データベース初期化
    initializer = DatabaseInitializer()
    initializer.initialize()


if __name__ == "__main__":
    main()