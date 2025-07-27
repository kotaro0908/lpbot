# add_liquidity.py - 堅牢ガス管理システム復活版
from web3 import Web3
from env_config import USDC_ADDRESS, WETH_ADDRESS
import json, os, time
import subprocess

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
RPC_URL = "https://arb1.arbitrum.io/rpc"

# 無制限approve用定数
MAX_UINT256 = 2 ** 256 - 1

# 堅牢ガス管理設定
ROBUST_GAS_CONFIG = {
    "base_gas": 588315,  # 実績ベース
    "max_retries": 3,  # 最大リトライ回数
    "gas_multipliers": [1.0, 1.5, 2.0, 3.0],  # 段階的ガス増加
    "retry_delays": [5, 15, 30],  # リトライ間隔（秒）
    "gas_price": "2 gwei"  # 基本ガス価格
}

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

POSITION_MANAGER_ABI = [
    {"inputs": [{"components": [{"internalType": "address", "name": "token0", "type": "address"},
                                {"internalType": "address", "name": "token1", "type": "address"},
                                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                                {"internalType": "int24", "name": "tickLower", "type": "int24"},
                                {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                                {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                                {"internalType": "address", "name": "recipient", "type": "address"},
                                {"internalType": "uint256", "name": "deadline", "type": "uint256"}],
                 "internalType": "struct INonfungiblePositionManager.MintParams", "name": "params", "type": "tuple"}],
     "name": "mint", "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                                 {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                                 {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                                 {"internalType": "uint256", "name": "amount1", "type": "uint256"}],
     "stateMutability": "payable", "type": "function"}
]


class RobustGasManager:
    """堅牢ガス管理システム"""

    def __init__(self, web3, max_retries=3):
        self.web3 = web3
        self.max_retries = max_retries
        self.gas_multipliers = ROBUST_GAS_CONFIG["gas_multipliers"]
        self.retry_delays = ROBUST_GAS_CONFIG["retry_delays"]
        self.base_gas = ROBUST_GAS_CONFIG["base_gas"]

    def execute_with_gas_resilience(self, transaction_func, *args, **kwargs):
        """ガス不足耐性付きトランザクション実行"""

        for attempt in range(self.max_retries + 1):
            try:
                print(f"=== LP Mint 実行試行 {attempt + 1}/{self.max_retries + 1} ===")

                # ガス設定計算
                gas_multiplier = self.gas_multipliers[min(attempt, len(self.gas_multipliers) - 1)]
                current_gas = int(self.base_gas * gas_multiplier)
                gas_price = self.web3.to_wei("2", "gwei")

                print(f"   ガス設定: {current_gas:,} / {gas_price / 10 ** 9:.1f} gwei")
                print(f"   戦略: 試行{attempt + 1}: ガス×{gas_multiplier}")

                # トランザクション実行
                result = transaction_func(current_gas, gas_price, *args, **kwargs)

                if result["success"]:
                    print(f"✅ 成功! (試行{attempt + 1}回目)")
                    efficiency = (result["gas_used"] / current_gas) * 100
                    print(f"🎉 最終成功! ({attempt + 1}回目で成功)")
                    print(f"   ガス使用量: {result['gas_used']:,}")
                    print(f"   効率: {efficiency:.1f}%")
                    return result
                else:
                    print(f"❌ 試行{attempt + 1}失敗: {result.get('error', 'Unknown error')}")

            except ValueError as e:
                error_msg = str(e)
                print(f"❌ 試行{attempt + 1}でエラー: {error_msg}")

                # ガス不足の判定
                if "insufficient funds for gas" in error_msg or "out of gas" in error_msg:
                    if attempt < self.max_retries:
                        delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                        print(f"⏳ ガス不足検知 - {delay}秒後に再試行...")
                        time.sleep(delay)
                        continue
                    else:
                        print("💀 最大リトライ回数に達しました")
                        return {"success": False, "error": "ガス不足 - 最大リトライ回数超過"}
                else:
                    print(f"💀 予期しないエラー: {error_msg}")
                    return {"success": False, "error": error_msg}

            except Exception as e:
                print(f"❌ 試行{attempt + 1}で例外: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    print(f"⏳ {delay}秒後に再試行...")
                    time.sleep(delay)
                else:
                    return {"success": False, "error": str(e)}

        return {"success": False, "error": "全ての試行が失敗"}


def execute_mint_with_robust_gas(gas_limit, gas_price, w3, wallet, params):
    """堅牢ガス管理でmint実行"""
    try:
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.mint(params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"   Tx Hash: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        return {
            "success": receipt.status == 1,
            "tx_hash": tx_hash.hex(),
            "gas_used": receipt.gasUsed,
            "events": len(receipt.logs)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def check_unlimited_approve_status(w3, wallet):
    """無制限approve状況の確認"""
    print("=== 🔍 無制限approve状況確認 ===")

    status = {}
    for token_name, token_address in [("WETH", WETH_ADDRESS), ("USDC", USDC_ADDRESS)]:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        allowance = token_contract.functions.allowance(wallet.address, POSITION_MANAGER_ADDRESS).call()

        # 無制限かどうかの判定（MAX_UINT256の50%以上なら無制限とみなす）
        is_unlimited = allowance >= MAX_UINT256 // 2
        status[token_name] = {
            "address": token_address,
            "allowance": allowance,
            "is_unlimited": is_unlimited
        }

        print(f"{token_name}: {'✅ 無制限設定済み' if is_unlimited else '❌ 有限設定'}")
        if not is_unlimited:
            print(f"  現在allowance: {allowance / (10 ** 18 if token_name == 'WETH' else 10 ** 6):.6f}")

    return status


def setup_unlimited_approve(w3, wallet, token_address, token_name):
    """指定トークンの無制限approve設定"""
    print(f"=== 🚀 {token_name} 無制限approve設定 ===")

    try:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # 現在のallowance確認
        current_allowance = token_contract.functions.allowance(
            wallet.address, POSITION_MANAGER_ADDRESS
        ).call()

        if current_allowance >= MAX_UINT256 // 2:
            print(f"✅ {token_name}: 既に無制限設定済み")
            return True

        print(f"🔧 {token_name}: 無制限approve実行中...")

        # 無制限approve実行
        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        approve_tx = token_contract.functions.approve(
            POSITION_MANAGER_ADDRESS,
            MAX_UINT256
        ).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": w3.to_wei("2", "gwei"),
            "value": 0
        })

        signed = wallet.sign_transaction(approve_tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"📝 Approve Tx: {tx_hash.hex()}")

        # 確認待機
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            print(f"✅ {token_name}: 無制限approve完了！")
            print(f"🎉 今後の{token_name}はapprove不要")
            return True
        else:
            print(f"❌ {token_name}: approve失敗")
            return False

    except Exception as e:
        print(f"❌ {token_name} approve実行エラー: {e}")
        return False


def setup_all_unlimited_approves(w3, wallet):
    """全トークンの無制限approve一括設定"""
    print("=== 🏆 Uniswap V3 完全無制限approve設定 ===")
    print("🎯 対象: WETH, USDC")
    print("🚀 効果: 今後のLP操作でapprove問題完全解決")

    success_count = 0

    # 必須トークン（WETH, USDC）
    essential_tokens = [("WETH", WETH_ADDRESS), ("USDC", USDC_ADDRESS)]

    for token_name, token_address in essential_tokens:
        if setup_unlimited_approve(w3, wallet, token_address, token_name):
            success_count += 1

    print(f"\n=== 📊 無制限approve設定結果 ===")
    print(f"成功: {success_count}/{len(essential_tokens)} トークン")

    if success_count == len(essential_tokens):
        print("🎉🎉🎉 完全成功！ 🎉🎉🎉")
        print("✅ WETH: 無制限approve完了")
        print("✅ USDC: 無制限approve完了")
        print("🚀 今後のUniswap V3操作でapprove問題ゼロ！")
        print("📈 利用可能: 全てのETH/USDCプール（全fee tier）")
        return True
    else:
        print("⚠️ 一部失敗 - 再実行を推奨")
        return False


def robust_lp_mint_test():
    """堅牢ガス管理システムでのLP追加テスト"""
    print("=== 🛡️ 堅牢ガス管理システム LP追加テスト ===")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise Exception("Web3接続失敗")

    # ウォレット設定
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("PRIVATE_KEY環境変数が設定されていません")

    wallet = w3.eth.account.from_key(private_key)

    print("=== Step 1: レンジ分析実行 ===")
    # range_analyzer.py実行
    result = subprocess.run(
        ["python", "range_analyzer.py"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ レンジ分析失敗: {result.stderr}")
        return

    print("✅ レンジ分析完了")

    print("=== Step 2: レンジ読み込み ===")
    # range_config.json読み込み
    with open("range_config.json", "r") as f:
        range_config = json.load(f)

    tick_lower = range_config["lower_tick"]
    tick_upper = range_config["upper_tick"]

    print(f"使用レンジ: {tick_lower} ～ {tick_upper}")

    print("=== Step 3: 残高確認 ===")
    # 残高確認
    weth_contract = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
    usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)

    weth_balance = weth_contract.functions.balanceOf(wallet.address).call()
    usdc_balance = usdc_contract.functions.balanceOf(wallet.address).call()
    eth_balance = w3.eth.get_balance(wallet.address)

    print(f"残高:")
    print(f"  WETH: {weth_balance / 10 ** 18:.6f}")
    print(f"  USDC: {usdc_balance / 10 ** 6:.2f}")
    print(f"  ETH: {eth_balance / 10 ** 18:.6f}")

    print("=== Step 4: 投入金額設定 ===")
    # 投入金額（小額テスト）
    amount0_desired = int(0.001 * 10 ** 18)  # 0.001 WETH
    amount1_desired = int(3.76 * 10 ** 6)  # 3.76 USDC
    amount0_min = 1  # 最小限
    amount1_min = 1  # 最小限

    print(f"投入予定: {amount0_desired / 10 ** 18:.6f} WETH, {amount1_desired / 10 ** 6:.2f} USDC")

    # 残高チェック
    if weth_balance < amount0_desired or usdc_balance < amount1_desired:
        print(f"❌ 残高不足")
        return

    print("=== Step 5: approve状況確認 ===")
    approve_status = check_unlimited_approve_status(w3, wallet)

    # 無制限approve未設定なら設定を提案
    need_setup = False
    for token_name, status in approve_status.items():
        if not status["is_unlimited"]:
            need_setup = True
            break

    if need_setup:
        print("⚠️ 無制限approve未設定のトークンがあります")
        print("🔧 無制限approve設定を実行しますか？")
        response = input("実行する場合は 'yes' を入力: ")

        if response.lower() == 'yes':
            if not setup_all_unlimited_approves(w3, wallet):
                print("❌ 無制限approve設定失敗")
                return
        else:
            print("❌ 無制限approve設定をスキップ - LP追加を中断")
            return
    else:
        print("✅ 全て無制限approve設定済み - approve処理スキップ")

    print("=== Step 6: 堅牢ガス管理でLP追加実行 ===")

    # パラメータ準備
    deadline = int(time.time()) + 3600

    params = (
        WETH_ADDRESS,  # token0
        USDC_ADDRESS,  # token1
        500,  # fee
        tick_lower,  # tickLower
        tick_upper,  # tickUpper
        amount0_desired,  # amount0Desired
        amount1_desired,  # amount1Desired
        amount0_min,  # amount0Min
        amount1_min,  # amount1Min
        wallet.address,  # recipient
        deadline  # deadline
    )

    # 堅牢ガス管理システム初期化
    gas_manager = RobustGasManager(w3, max_retries=3)

    print("🛡️ 堅牢ガス管理システム開始")
    print(f"📊 基本ガス: {ROBUST_GAS_CONFIG['base_gas']:,}")
    print(f"🔄 最大リトライ: {ROBUST_GAS_CONFIG['max_retries']}回")
    print(f"📈 ガス倍率: {ROBUST_GAS_CONFIG['gas_multipliers']}")

    # 堅牢mint実行
    result = gas_manager.execute_with_gas_resilience(
        execute_mint_with_robust_gas,
        w3, wallet, params
    )

    print("\n=== 📊 最終実行結果 ===")
    if result["success"]:
        print(f"Status: ✅ SUCCESS")
        print(f"Gas Used: {result['gas_used']:,}")
        print(f"Events: {result['events']} 個")
        print(f"Tx Hash: {result['tx_hash']}")
        print("🎉🎉🎉 堅牢ガス管理システム LP追加成功！ 🎉🎉🎉")
        print("🛡️ ガス不足・エラー耐性完備")
        print("🚀 本番運用レベルの信頼性達成")
    else:
        print(f"Status: ❌ FAILED")
        print(f"Error: {result['error']}")
        print("💀 堅牢システムでも失敗 - 詳細確認が必要")


def main():
    """メイン実行関数"""
    print("=== 🏆 Uniswap V3 堅牢ガス管理版 LP自動化 ===")
    print("🎯 目標: ガス不足・エラー完全対応")
    print("🛡️ 効果: 本番運用レベルの信頼性")

    choice = input("\n実行モードを選択:\n1: 無制限approve設定のみ\n2: 堅牢LP追加テスト\n3: 両方実行\n選択 (1/2/3): ")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise Exception("Web3接続失敗")

    # ウォレット設定
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("PRIVATE_KEY環境変数が設定されていません")

    wallet = w3.eth.account.from_key(private_key)

    if choice == "1":
        # 無制限approve設定のみ
        setup_all_unlimited_approves(w3, wallet)
    elif choice == "2":
        # 堅牢LP追加テストのみ
        robust_lp_mint_test()
    elif choice == "3":
        # 両方実行
        if setup_all_unlimited_approves(w3, wallet):
            print("\n" + "=" * 50)
            robust_lp_mint_test()
    else:
        print("❌ 無効な選択")


if __name__ == "__main__":
    main()