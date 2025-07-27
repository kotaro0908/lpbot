# lp_manager.py - LP自動リバランス機能（完全版）
import subprocess
import json
import time
from logger import log_info, log_error

# 定数
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
MAX_UINT256 = 2 ** 256 - 1

# Position Manager ABI（必要な関数のみ）
POSITION_MANAGER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "positions",
     "outputs": [{"internalType": "uint96", "name": "nonce", "type": "uint96"},
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
                 {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}], "stateMutability": "view",
     "type": "function"},
    {"inputs": [{"components": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                                {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                                {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                                {"internalType": "uint256", "name": "deadline", "type": "uint256"}],
                 "internalType": "struct INonfungiblePositionManager.DecreaseLiquidityParams", "name": "params",
                 "type": "tuple"}], "name": "decreaseLiquidity",
     "outputs": [{"internalType": "uint256", "name": "amount0", "type": "uint256"},
                 {"internalType": "uint256", "name": "amount1", "type": "uint256"}], "stateMutability": "payable",
     "type": "function"},
    {"inputs": [{"components": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                                {"internalType": "address", "name": "recipient", "type": "address"},
                                {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                                {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}],
                 "internalType": "struct INonfungiblePositionManager.CollectParams", "name": "params",
                 "type": "tuple"}], "name": "collect",
     "outputs": [{"internalType": "uint256", "name": "amount0", "type": "uint256"},
                 {"internalType": "uint256", "name": "amount1", "type": "uint256"}], "stateMutability": "payable",
     "type": "function"}
]


def remove_liquidity(web3, wallet, token_id):
    """LP撤退関数（実際の実装）"""
    try:
        pm = web3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        # 現在のポジション情報を取得
        position_data = pm.functions.positions(token_id).call()
        liquidity = position_data[7]  # liquidity

        if liquidity == 0:
            return {"success": False, "error": "No liquidity to remove"}

        deadline = int(time.time()) + 3600

        # DecreaseLiquidity params
        decrease_params = (
            token_id,  # tokenId
            liquidity,  # liquidity (全量撤退)
            0,  # amount0Min
            0,  # amount1Min
            deadline  # deadline
        )

        nonce = web3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.decreaseLiquidity(decrease_params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": 400000,
            "gasPrice": web3.to_wei("2", "gwei"),
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        return {
            "success": receipt.status == 1,
            "tx_hash": tx_hash.hex(),
            "gas_used": receipt.gasUsed
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def collect_fees(web3, wallet, token_id):
    """手数料収集関数（実際の実装）"""
    try:
        pm = web3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        # Collect params
        collect_params = (
            token_id,  # tokenId
            wallet.address,  # recipient
            MAX_UINT256,  # amount0Max
            MAX_UINT256  # amount1Max
        )

        nonce = web3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.collect(collect_params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": web3.to_wei("2", "gwei"),
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        return {
            "success": receipt.status == 1,
            "tx_hash": tx_hash.hex(),
            "gas_used": receipt.gasUsed
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def add_liquidity_via_script():
    """add_liquidity.pyスクリプト経由でLP追加"""
    try:
        # add_liquidity.pyを外部スクリプトとして実行
        result = subprocess.run(
            ["python", "add_liquidity.py"],
            capture_output=True,
            text=True,
            input="2\n"  # モード2（LP追加テスト）を選択
        )

        success = "SUCCESS" in result.stdout

        return {
            "success": success,
            "output": result.stdout,
            "error": result.stderr if not success else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_lp_position(web3, wallet, token_id):
    """LP NFTポジション情報取得（実際の実装）"""
    try:
        pm = web3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        position_data = pm.functions.positions(token_id).call()

        return {
            "success": True,
            "token_id": token_id,
            "nonce": position_data[0],
            "operator": position_data[1],
            "token0": position_data[2],
            "token1": position_data[3],
            "fee": position_data[4],
            "tick_lower": position_data[5],
            "tick_upper": position_data[6],
            "liquidity": position_data[7],
            "fee_growth_inside0": position_data[8],
            "fee_growth_inside1": position_data[9],
            "tokens_owed0": position_data[10],
            "tokens_owed1": position_data[11]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_current_tick_from_pool(web3, pool_address):
    """プールから現在tickを取得"""
    try:
        pool_abi = [
            {"inputs": [], "name": "slot0",
             "outputs": [{"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                         {"internalType": "int24", "name": "tick", "type": "int24"},
                         {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                         {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                         {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                         {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                         {"internalType": "bool", "name": "unlocked", "type": "bool"}], "stateMutability": "view",
             "type": "function"}
        ]

        pool_contract = web3.eth.contract(address=pool_address, abi=pool_abi)
        slot0 = pool_contract.functions.slot0().call()
        current_tick = slot0[1]

        return current_tick

    except Exception as e:
        log_error(f"現在tick取得エラー: {e}")
        return None


class LPManager:
    def __init__(self, web3, wallet, pool_address, config):
        self.web3 = web3
        self.wallet = wallet
        self.pool_address = pool_address  # プールアドレスを明確に
        self.config = config

    def withdraw_and_redeploy(self, token_id):
        """LP撤退→手数料回収→再投入の自動実行"""
        try:
            log_info(f"=== LP自動リバランス開始 (NFT: {token_id}) ===")

            # 1. 現在のLPポジションを撤退
            remove_result = remove_liquidity(self.web3, self.wallet, token_id)
            if remove_result["success"]:
                log_info(f"✅ LP撤退完了 (NFT: {token_id})")
                log_info(f"   Tx: {remove_result['tx_hash']}")
            else:
                log_error(f"❌ LP撤退失敗: {remove_result['error']}")
                return False

            # 2. 手数料回収
            collect_result = collect_fees(self.web3, self.wallet, token_id)
            if collect_result["success"]:
                log_info(f"✅ 手数料回収完了 (NFT: {token_id})")
                log_info(f"   Tx: {collect_result['tx_hash']}")
            else:
                log_error(f"❌ 手数料回収失敗: {collect_result['error']}")

            # 3. 必要に応じてスワップ（将来実装）
            # self.swap_tokens_if_needed()

            # 4. range_analyzer.pyで新しいレンジを計算
            log_info("📊 新しいレンジを計算中...")
            analyzer_result = subprocess.run(
                ["python", "range_analyzer.py"],
                capture_output=True, text=True
            )

            if analyzer_result.returncode == 0:
                log_info("✅ レンジ計算完了")
            else:
                log_error(f"❌ レンジ計算失敗: {analyzer_result.stderr}")
                return False

            # 5. 新しいレンジでLP追加
            log_info("🚀 新しいレンジでLP追加中...")
            add_result = add_liquidity_via_script()

            if add_result["success"]:
                log_info("✅ LP再投入完了")
                log_info("🎉 自動リバランス完了！")
                return True
            else:
                log_error(f"❌ LP再投入失敗: {add_result['error']}")
                return False

        except Exception as e:
            log_error(f"❌ LP自動リバランスエラー: {str(e)}")
            return False

    def get_current_position(self, token_id):
        """現在のLPポジション情報を取得"""
        return get_lp_position(self.web3, self.wallet, token_id)

    def is_position_out_of_range(self, token_id):
        """ポジションが価格レンジ外かどうかをチェック"""
        try:
            # ポジション情報取得
            position = self.get_current_position(token_id)
            if not position["success"]:
                return False

            # 現在tick取得
            current_tick = get_current_tick_from_pool(self.web3, self.pool_address)
            if current_tick is None:
                return False

            # レンジ外判定
            tick_lower = position["tick_lower"]
            tick_upper = position["tick_upper"]

            is_out_of_range = current_tick <= tick_lower or current_tick >= tick_upper

            log_info(f"📊 レンジチェック:")
            log_info(f"   現在tick: {current_tick}")
            log_info(f"   レンジ: {tick_lower} ～ {tick_upper}")
            log_info(f"   判定: {'❌ レンジ外' if is_out_of_range else '✅ レンジ内'}")

            return is_out_of_range

        except Exception as e:
            log_error(f"レンジ外判定エラー: {e}")
            return False

    def monitor_and_rebalance(self, token_id):
        """監視→必要時自動リバランス"""
        try:
            log_info(f"=== LP監視開始 (NFT: {token_id}) ===")

            if self.is_position_out_of_range(token_id):
                log_info("🔄 レンジ外のため自動リバランス実行")
                return self.withdraw_and_redeploy(token_id)
            else:
                log_info("✅ レンジ内のため継続監視")
                return True

        except Exception as e:
            log_error(f"監視・リバランスエラー: {e}")
            return False


def main():
    """テスト実行用メイン関数"""
    print("=== 🔄 LP Manager テスト実行 ===")

    # 設定表示
    pool_address = "0xC6962004f452bE9203591991D15f6b388e09E8D0"  # ETH/USDC 0.05%
    print(f"対象プール: {pool_address}")
    print(f"Position Manager: {POSITION_MANAGER_ADDRESS}")

    # Web3接続テスト
    try:
        from web3 import Web3
        import os

        # .envファイル読み込み
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            print("💡 python-dotenvがインストールされていません（オプション）")

        RPC_URL = "https://arb1.arbitrum.io/rpc"
        w3 = Web3(Web3.HTTPProvider(RPC_URL))

        if w3.is_connected():
            print("✅ Web3接続成功")
            print(f"   最新ブロック: {w3.eth.block_number}")
        else:
            print("❌ Web3接続失敗")
            return

        # ウォレット設定テスト
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            print("❌ PRIVATE_KEY環境変数が設定されていません")
            print("💡 解決方法:")
            print("   1. export PRIVATE_KEY='your_key' を実行")
            print("   2. または.envファイルにPRIVATE_KEY=your_key を記載")
            print("   3. または source .env を実行")
            return

        wallet = w3.eth.account.from_key(private_key)
        print(f"✅ ウォレット設定成功")
        print(f"   アドレス: {wallet.address}")

        # 残高確認
        eth_balance = w3.eth.get_balance(wallet.address)
        print(f"   ETH残高: {eth_balance / 10 ** 18:.6f} ETH")

        # LPManagerインスタンス作成テスト
        config = {
            "rebalance_threshold": 0.05,
            "monitor_interval": 300
        }

        manager = LPManager(w3, wallet, pool_address, config)
        print("✅ LPManagerインスタンス作成成功")

        # 現在tick取得テスト
        current_tick = get_current_tick_from_pool(w3, pool_address)
        if current_tick is not None:
            print(f"✅ 現在tick取得成功: {current_tick}")
        else:
            print("❌ 現在tick取得失敗")

        # 機能選択メニュー
        print("\n=== 📋 実行可能な機能 ===")
        print("1: 現在tick確認のみ")
        print("2: NFTポジション情報確認")
        print("3: レンジ外判定テスト")
        print("4: LP自動リバランステスト")
        print("5: 終了")

        choice = input("\n選択 (1-5): ").strip()

        if choice == "1":
            print(f"\n📊 現在の市場状況:")
            print(f"プールアドレス: {pool_address}")
            print(f"現在tick: {current_tick}")
            # tick to price conversion (簡易版)
            if current_tick is not None:
                price = 1.0001 ** current_tick  # USDC/WETH price
                print(f"概算価格(USDC/WETH): {price:.2f}")
                print(f"概算価格(ETH/USDC): {1 / price:.2f}")

        elif choice == "2":
            token_id = input("NFT Token ID を入力 (例: 4710571): ").strip()
            if token_id.isdigit():
                position = manager.get_current_position(int(token_id))
                if position["success"]:
                    print(f"\n📊 NFT {token_id} ポジション情報:")
                    print(f"   Token0: {position['token0']}")
                    print(f"   Token1: {position['token1']}")
                    print(f"   Fee: {position['fee']}")
                    print(f"   Tick範囲: {position['tick_lower']} ～ {position['tick_upper']}")
                    print(f"   流動性: {position['liquidity']}")
                    print(f"   手数料0: {position['tokens_owed0']}")
                    print(f"   手数料1: {position['tokens_owed1']}")
                else:
                    print(f"❌ NFT {token_id} 情報取得失敗: {position['error']}")
            else:
                print("❌ 無効なToken ID")

        elif choice == "3":
            token_id = input("NFT Token ID を入力 (例: 4710571): ").strip()
            if token_id.isdigit():
                is_out = manager.is_position_out_of_range(int(token_id))
                print(f"\n📊 レンジ外判定結果: {'❌ レンジ外' if is_out else '✅ レンジ内'}")
            else:
                print("❌ 無効なToken ID")

        elif choice == "4":
            token_id = input("NFT Token ID を入力 (例: 4710571): ").strip()
            if token_id.isdigit():
                print(f"\n🔄 LP自動リバランステスト開始...")
                print("⚠️ これは実際のトランザクションを実行します")
                confirm = input("実行しますか？ (yes/no): ").strip().lower()

                if confirm == "yes":
                    result = manager.monitor_and_rebalance(int(token_id))
                    if result:
                        print("✅ 自動リバランス完了")
                    else:
                        print("❌ 自動リバランス失敗")
                else:
                    print("キャンセルしました")
            else:
                print("❌ 無効なToken ID")

        elif choice == "5":
            print("終了します")

        else:
            print("❌ 無効な選択")

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

# 使用例（他のスクリプトから呼び出し）
"""
from lp_manager import LPManager

# 設定
pool_address = "0xC6962004f452bE9203591991D15f6b388e09E8D0"  # ETH/USDC 0.05%
config = {
    "rebalance_threshold": 0.05,  # 5%レンジ外で実行
    "monitor_interval": 300       # 5分間隔
}

manager = LPManager(web3, wallet, pool_address, config)

# 現在のNFT IDを取得（別途実装が必要）
current_token_id = 4710571  # 例

# 監視・自動リバランス実行
manager.monitor_and_rebalance(current_token_id)
"""