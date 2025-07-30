#!/usr/bin/env python3
"""
LP BOT監視システム - 外部データコレクター
Etherscan Multichain APIからトランザクション詳細と手数料収益を取得
"""

import os
import sys
import json
import time
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

# 設定
ARBISCAN_API_KEY = os.getenv("ARBISCAN_API_KEY")
# Etherscan Multichain APIのエンドポイントを使用
ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
ARBITRUM_CHAIN_ID = 42161  # Arbitrum OneのチェーンID
DB_PATH = Path(__file__).parent.parent / "lpbot.db"

# Uniswap V3 Position Manager
POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# レート制限（5 calls/sec）
RATE_LIMIT_DELAY = 0.25  # 4 calls/secで安全マージン


class ExternalDataCollector:
    """外部データ収集クラス"""

    def __init__(self, api_key=ARBISCAN_API_KEY, db_path=DB_PATH):
        self.api_key = api_key
        self.db_path = db_path
        self.conn = None

        # デバッグ: APIキーの存在確認
        print(f"🔑 APIキー: {'設定済み' if self.api_key else '未設定'}")
        print(f"   キーの長さ: {len(self.api_key) if self.api_key else 0}")

        if not self.api_key:
            raise ValueError("ARBISCAN_API_KEY が設定されていません")

    def connect_db(self):
        """データベース接続"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close_db(self):
        """データベース切断"""
        if self.conn:
            self.conn.close()

    def test_api_connection(self):
        """API接続テスト"""
        print("🔍 Etherscan Multichain API接続テスト中...")

        # Multichain API用のパラメータ
        params = {
            "chainid": ARBITRUM_CHAIN_ID,
            "module": "account",
            "action": "balance",
            "address": POSITION_MANAGER,
            "tag": "latest",
            "apikey": self.api_key
        }

        try:
            response = requests.get(ETHERSCAN_API_URL, params=params, timeout=10)
            data = response.json()

            # デバッグ情報
            print(f"📊 APIレスポンス: {data}")

            if data.get("status") == "1":
                balance = int(data["result"]) / 10 ** 18
                print(f"✅ API接続成功！")
                print(f"   Position Manager ETH残高: {balance:.6f} ETH")
                return True
            else:
                print(f"❌ APIエラー: {data.get('message', 'Unknown error')}")
                print(f"   詳細: {data}")
                return False

        except Exception as e:
            print(f"❌ 接続エラー: {e}")
            return False

    def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """トランザクション詳細を取得"""
        print(f"📊 トランザクション詳細取得: {tx_hash[:10]}...")

        # トランザクションレシート取得
        params = {
            "chainid": ARBITRUM_CHAIN_ID,
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": self.api_key
        }

        try:
            response = requests.get(ETHERSCAN_API_URL, params=params, timeout=10)
            data = response.json()

            if "result" in data and data["result"]:
                result = data["result"]

                # ガス情報抽出
                gas_used = int(result["gasUsed"], 16)
                effective_gas_price = int(result.get("effectiveGasPrice", "0"), 16)

                # ガス代計算（ETH）
                gas_cost_wei = gas_used * effective_gas_price
                gas_cost_eth = gas_cost_wei / 10 ** 18

                # ブロック情報
                block_number = int(result["blockNumber"], 16)

                return {
                    "tx_hash": tx_hash,
                    "gas_used": gas_used,
                    "gas_price": effective_gas_price / 10 ** 9,  # Gwei
                    "gas_cost_eth": gas_cost_eth,
                    "block_number": block_number,
                    "status": int(result["status"], 16)
                }
            else:
                print(f"⚠️  トランザクションが見つかりません: {tx_hash}")
                return None

        except Exception as e:
            print(f"❌ 取得エラー: {e}")
            return None
        finally:
            # レート制限対策
            time.sleep(RATE_LIMIT_DELAY)

    def get_eth_price_at_block(self, block_number: int) -> Optional[float]:
        """特定ブロックでのETH価格を取得（Uniswap V3プールから）"""
        print(f"💱 ETH価格取得中... (ブロック: {block_number})")

        # Uniswap V3 USDC/WETH プール
        POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"

        # slot0()関数のセレクタ
        slot0_selector = "0x3850c7bd"

        params = {
            "chainid": ARBITRUM_CHAIN_ID,
            "module": "proxy",
            "action": "eth_call",
            "to": POOL_ADDRESS,
            "data": slot0_selector,
            "tag": hex(block_number),  # 特定ブロックでの価格
            "apikey": self.api_key
        }

        try:
            response = requests.get(ETHERSCAN_API_URL, params=params, timeout=10)
            data = response.json()

            # Etherscan V2 APIのレスポンス形式に対応
            if "result" in data and data["result"]:
                result = data["result"]

                # resultは0xから始まる16進数文字列
                if result.startswith("0x"):
                    result = result[2:]  # 0xを削除

                # sqrtPriceX96は最初の32バイト（64文字）
                sqrt_price_x96_hex = result[:64]
                sqrt_price_x96 = int(sqrt_price_x96_hex, 16)

                # 価格計算（USDC per WETH）
                price = (sqrt_price_x96 / (2 ** 96)) ** 2
                eth_price_usd = price * (10 ** 12)  # USDC decimals adjustment

                print(f"   ETH価格: ${eth_price_usd:.2f}")
                return eth_price_usd
            else:
                print(f"⚠️  価格取得失敗、デフォルト値使用")
                return 3900.0

        except Exception as e:
            print(f"❌ 価格取得エラー: {e}")
            return 3900.0
        finally:
            time.sleep(RATE_LIMIT_DELAY)

    def update_rebalance_gas_info(self, tx_hash: str):
        """リバランス履歴のガス情報を更新（重複対応版）"""

        # 既にガス情報が入っているレコードがあるかチェック
        cursor = self.conn.execute("""
                                   SELECT COUNT(*)FROM rebalance_history 
            WHERE tx_hash = ? AND gas_used IS NOT NULL
        """, (tx_hash,))

        if cursor.fetchone()[0] > 0:
            print(f"⏭️  スキップ: {tx_hash[:10]}... (既に処理済み)")
            return True

        # トランザクション詳細取得
        tx_details = self.get_transaction_details(tx_hash)

        if not tx_details:
            return False

        # ETH価格取得（仮）
        eth_price = self.get_eth_price_at_block(tx_details["block_number"])
        gas_cost_usd = tx_details["gas_cost_eth"] * eth_price

        try:
            # データベースに列を追加（必要な場合）
            self.conn.execute("""
                              ALTER TABLE rebalance_history
                                  ADD COLUMN gas_cost_eth REAL
                              """)
            self.conn.execute("""
                              ALTER TABLE rebalance_history
                                  ADD COLUMN gas_cost_usd REAL
                              """)
        except:
            # 既に列が存在する場合は無視
            pass

        try:
            # 重複レコードがある場合、最初の1件だけ更新
            self.conn.execute("""
                              UPDATE rebalance_history
                              SET gas_used     = ?,
                                  gas_price    = ?,
                                  gas_cost_eth = ?,
                                  gas_cost_usd = ?
                              WHERE tx_hash = ?
                                AND rowid = (SELECT MIN(rowid)
                                             FROM rebalance_history
                                             WHERE tx_hash = ?)
                              """, (
                                  tx_details["gas_used"],
                                  tx_details["gas_price"],
                                  tx_details["gas_cost_eth"],
                                  gas_cost_usd,
                                  tx_hash,
                                  tx_hash
                              ))

            self.conn.commit()
            print(f"✅ ガス情報更新完了: {tx_hash[:10]}... (最初のレコードのみ)")
            print(f"   ガス使用量: {tx_details['gas_used']:,}")
            print(f"   ガス価格: {tx_details['gas_price']:.2f} Gwei")
            print(f"   ガス代: {tx_details['gas_cost_eth']:.6f} ETH (${gas_cost_usd:.2f})")

            return True

        except Exception as e:
            print(f"❌ DB更新エラー: {e}")
            return False

    def collect_missing_gas_data(self):
        """ガス情報が欠けているトランザクションを収集"""
        print("\n🔍 ガス情報未取得のトランザクションを検索中...")

        # DISTINCTを追加して重複を最初から除外
        cursor = self.conn.execute("""
                                   SELECT DISTINCT tx_hash
                                   FROM rebalance_history
                                   WHERE tx_hash IS NOT NULL
                                     AND gas_used IS NULL
                                   ORDER BY timestamp DESC
                                   """)

        tx_hashes = [row["tx_hash"] for row in cursor.fetchall()]

        if not tx_hashes:
            print("✅ 全てのトランザクションのガス情報は取得済みです")
            return

        print(f"📊 {len(tx_hashes)}件のトランザクションを処理します")

        success_count = 0
        for i, tx_hash in enumerate(tx_hashes, 1):
            print(f"\n[{i}/{len(tx_hashes)}] 処理中...")
            if self.update_rebalance_gas_info(tx_hash):
                success_count += 1

        print(f"\n✅ 完了: {success_count}/{len(tx_hashes)}件のガス情報を更新")

    def run_collection(self):
        """データ収集実行"""
        print(f"\n🚀 外部データ収集開始")
        print(f"📍 データベース: {self.db_path}")

        try:
            # API接続テスト
            if not self.test_api_connection():
                print("❌ API接続テスト失敗")
                return

            # データベース接続
            self.connect_db()

            # ガス情報収集
            self.collect_missing_gas_data()

            # TODO: 将来の実装
            # - Collect手数料収益の取得
            # - LP価値の計算
            # - 価格履歴の取得

            print("\n✅ 外部データ収集完了！")

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            raise
        finally:
            self.close_db()


def main():
    """メイン実行関数"""
    collector = ExternalDataCollector()
    collector.run_collection()


if __name__ == "__main__":
    main()