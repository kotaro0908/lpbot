#!/usr/bin/env python3
"""
強制リバランステスト
レンジ外れ→撤退→再LPの完全フロー実証用

使用方法:
1. 現在のmain.pyを停止
2. このスクリプトを実行してレンジ外れを強制発生
3. 完全フローの動作確認
"""

import os
import sys
import time
import json
import subprocess
import logging
from web3 import Web3
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# 設定
RPC_URL = os.getenv("RPC_URL")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# コントラクトアドレス
WETH_ADDRESS = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1"
USDC_ADDRESS = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class ForcedRebalanceTest:
    def __init__(self):
        """強制リバランステストの初期化"""
        print("=== 🧪 強制リバランステスト開始 ===")
        print("🎯 目的: レンジ外れ→撤退→再LPの完全フロー実証")
        print("⚠️  注意: テスト用の一時的な動作です")
        print()

        # Web3接続
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise Exception("Web3接続に失敗しました")

        self.wallet_address = self.w3.to_checksum_address(WALLET_ADDRESS)
        self.account = self.w3.eth.account.from_key(PRIVATE_KEY)

        # コントラクト設定
        self.setup_contracts()

        # 現在の追跡NFTを確認
        self.tracked_nfts = self.load_tracked_nfts()

        logging.info("✅ 強制リバランステスト初期化完了")

    def setup_contracts(self):
        """コントラクトの設定"""
        # Position Manager ABI（最小限）
        position_manager_abi = [
            {
                "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
                "name": "positions",
                "outputs": [
                    {"internalType": "uint96", "name": "nonce", "type": "uint96"},
                    {"internalType": "address", "name": "operator", "type": "address"},
                    {"internalType": "address", "name": "token0", "type": "address"},
                    {"internalType": "address", "name": "token1", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "int24", "name": "tickLower", "type": "int24"},
                    {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                    {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                    {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
                    {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
                    {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
                    {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        # Pool ABI（最小限）
        pool_abi = [
            {
                "inputs": [],
                "name": "slot0",
                "outputs": [
                    {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                    {"internalType": "int24", "name": "tick", "type": "int24"},
                    {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                    {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                    {"internalType": "bool", "name": "unlocked", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.position_manager = self.w3.eth.contract(
            address=POSITION_MANAGER_ADDRESS,
            abi=position_manager_abi
        )

        self.pool = self.w3.eth.contract(
            address=POOL_ADDRESS,
            abi=pool_abi
        )

    def load_tracked_nfts(self):
        """追跡中のNFTを読み込み"""
        try:
            with open('tracked_nfts.json', 'r') as f:
                data = json.load(f)
                return data.get('nft_ids', [])
        except:
            return []

    def get_current_tick(self):
        """現在のtickを取得"""
        try:
            slot0_result = self.pool.functions.slot0().call()
            return slot0_result[1]  # tick
        except Exception as e:
            logging.error(f"現在tick取得エラー: {e}")
            return None

    def get_nft_position_info(self, nft_id):
        """NFTのポジション情報を取得"""
        try:
            position = self.position_manager.functions.positions(nft_id).call()
            return {
                'nft_id': nft_id,
                'tick_lower': position[5],
                'tick_upper': position[6],
                'liquidity': position[7]
            }
        except Exception as e:
            logging.error(f"NFT {nft_id} 情報取得エラー: {e}")
            return None

    def simulate_range_check(self, current_tick, position_info, force_out_of_range=False):
        """レンジチェックのシミュレーション"""
        if force_out_of_range:
            logging.info("🧪 強制レンジ外れモード: レンジ外れを強制発生")
            return False  # 強制的にレンジ外れ判定

        # 通常のレンジチェック
        in_range = position_info['tick_lower'] <= current_tick <= position_info['tick_upper']
        return in_range

    def run_forced_rebalance_test(self):
        """強制リバランステストの実行"""
        print("🚀 強制リバランステスト開始...")
        print()

        if not self.tracked_nfts:
            print("❌ 追跡中のNFTがありません")
            print("💡 main.pyを先に実行してNFTを追跡状態にしてください")
            return False

        # 現在の状況確認
        current_tick = self.get_current_tick()
        if current_tick is None:
            print("❌ 現在tick取得に失敗しました")
            return False

        print(f"📊 現在tick: {current_tick}")
        print(f"🎯 追跡中NFT: {self.tracked_nfts}")
        print()

        # 各NFTの状況確認
        for nft_id in self.tracked_nfts:
            position_info = self.get_nft_position_info(nft_id)
            if not position_info:
                continue

            print(f"🔍 NFT {nft_id} 確認:")
            print(f"   流動性: {position_info['liquidity']}")
            print(f"   レンジ: [{position_info['tick_lower']}, {position_info['tick_upper']}]")

            # 通常のレンジチェック
            in_range = self.simulate_range_check(current_tick, position_info, force_out_of_range=False)
            print(f"   通常判定: {'✅ レンジ内' if in_range else '❌ レンジ外'}")

            # 強制レンジ外れチェック
            forced_out = self.simulate_range_check(current_tick, position_info, force_out_of_range=True)
            print(f"   強制判定: {'✅ レンジ内' if forced_out else '🧪 強制レンジ外'}")
            print()

        print("=== 🧪 強制リバランス実証準備完了 ===")
        print()
        print("📋 次のステップ:")
        print("1. main.pyのレンジ判定部分を一時的に修正")
        print("2. 強制レンジ外れ→完全リバランスフロー実行")
        print("3. 新NFT作成→追跡更新確認")
        print()

        return True

    def create_modified_main_py(self):
        """レンジ外れを強制するmain.pyの修正版を作成"""
        print("🔧 強制レンジ外れ版main.pyを作成中...")

        # main.pyを読み込み
        try:
            with open('main.py', 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ main.py読み込みエラー: {e}")
            return False

        # レンジ判定部分を強制外れに変更
        # "if current_tick < tick_lower or current_tick > tick_upper:" を探して置換
        original_condition = "if current_tick < tick_lower or current_tick > tick_upper:"
        forced_condition = "if True:  # 🧪 強制レンジ外れテスト"

        if original_condition in content:
            modified_content = content.replace(original_condition, forced_condition)

            # 修正版を保存
            with open('main_forced_rebalance.py', 'w', encoding='utf-8') as f:
                f.write(modified_content)

            print("✅ 強制レンジ外れ版main.py作成完了: main_forced_rebalance.py")
            print("🎯 実行コマンド: python main_forced_rebalance.py")
            print()
            print("⚠️  注意事項:")
            print("   - このスクリプトは即座にリバランスを実行します")
            print("   - 実際のトランザクションが発生します")
            print("   - テスト完了後は通常のmain.pyに戻してください")
            print()
            return True
        else:
            print("❌ レンジ判定条件が見つかりませんでした")
            print("💡 main.pyの構造が想定と異なる可能性があります")
            return False


def main():
    """メイン実行関数"""
    try:
        test = ForcedRebalanceTest()

        # 現在の状況確認とテスト準備
        if test.run_forced_rebalance_test():
            print("🤔 強制リバランステストを実行しますか？")
            print()
            print("📋 選択肢:")
            print("1. 修正版main.pyを作成（推奨）")
            print("2. 手動でmain.pyを修正する方法を表示")
            print("3. キャンセル")
            print()

            choice = input("選択してください (1/2/3): ").strip()

            if choice == "1":
                test.create_modified_main_py()
            elif choice == "2":
                print()
                print("🔧 手動修正方法:")
                print("1. main.pyをエディタで開く")
                print("2. 以下の行を探す:")
                print("   if current_tick < tick_lower or current_tick > tick_upper:")
                print("3. 以下に変更:")
                print("   if True:  # 強制レンジ外れテスト")
                print("4. 保存してpython main.pyを実行")
                print("5. テスト完了後は元に戻す")
                print()
            else:
                print("テストをキャンセルしました")

    except Exception as e:
        logging.error(f"テスト実行エラー: {e}")
        return False


if __name__ == "__main__":
    main()