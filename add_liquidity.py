#!/usr/bin/env python3
# add_liquidity.py - swap_utils統合版（NFT ID抽出機能付き + 引数対応 + 自動SWAP復活）
import sys
import argparse
from web3 import Web3
from env_config import USDC_ADDRESS, WETH_ADDRESS
import json, os, time
import subprocess
# ✅ swap_utils.py統合
from swap_utils import get_token_balance, swap_exact_input, approve_if_needed

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

# ✅ 設定値（デフォルト値、引数で上書き可能）
GAS_BUFFER_ETH = float(os.getenv("GAS_BUFFER_ETH", 0.005))  # ガスバッファ
MIN_LP_AMOUNT_WETH = float(os.getenv("MIN_LP_AMOUNT_WETH", 0.001))
MIN_LP_AMOUNT_USDC = float(os.getenv("MIN_LP_AMOUNT_USDC", 3.0))

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


# ✅ NFT ID抽出機能
def extract_nft_id_from_transaction(w3, tx_hash):
    """TransactionからNFT IDを抽出"""
    try:
        print(f"🔍 Transaction解析: NFT ID抽出中...")

        # トランザクションレシート取得（最大30秒待機）
        receipt = None
        for attempt in range(30):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                break
            except:
                print(f"   レシート取得試行 {attempt + 1}/30...")
                time.sleep(1)
                continue

        if not receipt:
            print("❌ トランザクションレシート取得失敗")
            return None

        # Transfer イベント検索
        transfer_signature = w3.keccak(text="Transfer(address,address,uint256)")

        for log in receipt.logs:
            if (log.address.lower() == POSITION_MANAGER_ADDRESS.lower() and
                    len(log.topics) >= 4 and
                    log.topics[0] == transfer_signature):

                # topic[1] = from, topic[2] = to, topic[3] = tokenId
                from_address = log.topics[1].hex()

                # Mint検出（from = 0x000...000）
                if from_address == "0x0000000000000000000000000000000000000000000000000000000000000000":
                    token_id = int(log.topics[3].hex(), 16)
                    print(f"✅ NFT Mint検出成功")
                    return token_id

        print("⚠️ NFT Mint イベントが見つかりませんでした")
        return None

    except Exception as e:
        print(f"❌ NFT ID抽出エラー: {e}")
        return None


# ✅ usable_weth計算（ETH + WETH - ガスバッファ）
def calculate_usable_weth(w3, wallet_address):
    """利用可能WETH計算（ETH + WETH - ガスバッファ）"""
    eth_balance = w3.eth.get_balance(wallet_address)
    weth_balance = get_token_balance(WETH_ADDRESS, wallet_address)

    eth_amount = eth_balance / 10 ** 18
    weth_amount = weth_balance / 10 ** 18

    # ガスバッファを考慮
    usable_eth = max(0, eth_amount - GAS_BUFFER_ETH)
    total_usable_weth = usable_eth + weth_amount

    print(f"💰 資産状況:")
    print(f"   ETH: {eth_amount:.6f}")
    print(f"   WETH: {weth_amount:.6f}")
    print(f"   ガスバッファ: {GAS_BUFFER_ETH}")
    print(f"   利用可能WETH: {total_usable_weth:.6f}")

    return {
        'eth_balance': eth_balance,
        'weth_balance': weth_balance,
        'usable_weth': total_usable_weth,
        'usable_eth': usable_eth
    }


# ✅ ETH→WETH自動変換
def ensure_weth_balance(w3, wallet, required_weth):
    """必要なWETH残高を確保（ETH→WETH自動変換）"""
    balances = calculate_usable_weth(w3, wallet.address)

    current_weth = balances['weth_balance'] / 10 ** 18
    required_amount = required_weth

    if current_weth >= required_amount:
        print(f"✅ WETH残高十分: {current_weth:.6f} >= {required_amount:.6f}")
        return True

    shortage = required_amount - current_weth
    available_eth = balances['usable_eth']

    if available_eth < shortage:
        print(f"❌ 資金不足: 必要{shortage:.6f} WETH, 利用可能ETH {available_eth:.6f}")
        return False

    print(f"🔄 ETH→WETH変換実行: {shortage:.6f} WETH")

    try:
        # ETHをWETHにラップ（簡易実装）
        # 注：実際のWRAP機能が必要（WETH contractのdeposit関数）
        print(f"📝 ETH→WETH変換中...")

        # WETH Contract deposit function
        weth_abi = [
            {
                "constant": False,
                "inputs": [],
                "name": "deposit",
                "outputs": [],
                "payable": True,
                "stateMutability": "payable",
                "type": "function"
            }
        ]

        weth_contract = w3.eth.contract(address=WETH_ADDRESS, abi=weth_abi)

        # ETH → WETH (deposit)
        shortage_wei = int(shortage * 10 ** 18)

        tx = weth_contract.functions.deposit().build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": 100000,
            "gasPrice": w3.to_wei("2", "gwei"),
            "value": shortage_wei
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"📝 ETH→WETH Tx: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ ETH→WETH変換成功: {shortage:.6f} WETH")
            return True
        else:
            print(f"❌ ETH→WETH変換失敗")
            return False

    except Exception as e:
        print(f"❌ ETH→WETH変換エラー: {e}")
        return False


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


# ✅ 引数対応版LP追加テスト（main.py連携対応 + 自動SWAP復活）
def robust_lp_mint_test(custom_eth_amount=None, custom_usdc_amount=None):
    """統合版LP追加テスト（引数対応版 + 自動SWAP復活）"""
    print("=== 🛡️ 統合版LP追加テスト（引数対応版 + 自動SWAP復活） ===")

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

    print("=== Step 3: 統合残高確認 ===")
    # ✅ 統合残高確認（usable_weth計算）
    balances = calculate_usable_weth(w3, wallet.address)
    usdc_balance = get_token_balance(USDC_ADDRESS, wallet.address)

    print(f"USDC残高: {usdc_balance / 10 ** 6:.2f}")

    print("=== Step 4: 投入金額設定 ===")
    # ✅ カスタム金額または設定値から投入金額決定
    if custom_eth_amount is not None and custom_usdc_amount is not None:
        print(f"💰 main.pyからの最適化投入額を使用")
        amount0_desired = int(custom_eth_amount * 10 ** 18)  # WETH
        amount1_desired = int(custom_usdc_amount * 10 ** 6)  # USDC
        target_weth = custom_eth_amount
        target_usdc = custom_usdc_amount
    else:
        print(f"📋 デフォルト設定値を使用")
        amount0_desired = int(MIN_LP_AMOUNT_WETH * 10 ** 18)  # WETH
        amount1_desired = int(MIN_LP_AMOUNT_USDC * 10 ** 6)  # USDC
        target_weth = MIN_LP_AMOUNT_WETH
        target_usdc = MIN_LP_AMOUNT_USDC

    amount0_min = 1  # 最小限
    amount1_min = 1  # 最小限

    print(f"投入予定: {amount0_desired / 10 ** 18:.6f} WETH, {amount1_desired / 10 ** 6:.2f} USDC")

    print("=== Step 5: 自動WETH確保 ===")
    # ✅ 必要なWETH残高を確保（ETH→WETH自動変換）
    if not ensure_weth_balance(w3, wallet, target_weth):
        print(f"❌ WETH確保失敗（ETH不足）")

        # 🆕 WETH不足時の自動SWAP
        print("=== Step 5.1: WETH不足時の自動SWAP ===")
        weth_balance = get_token_balance(WETH_ADDRESS, wallet.address)
        if weth_balance < amount0_desired:
            weth_shortage = amount0_desired - weth_balance
            weth_shortage_float = weth_shortage / 10 ** 18

            print(f"🔄 WETH不足検知: 不足額 {weth_shortage_float:.6f} WETH")

            # ETH価格取得
            eth_price = 3900  # フォールバック価格
            try:
                pool_abi = [
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                            {"internalType": "int24", "name": "tick", "type": "int24"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                pool_contract = w3.eth.contract(address=POOL_ADDRESS, abi=pool_abi)
                slot0 = pool_contract.functions.slot0().call()
                sqrt_price_x96 = slot0[0]
                price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
                eth_price = price_raw * (10 ** 12)
                if eth_price <= 0:
                    eth_price = 3900
            except:
                pass

            # 必要USDC量計算
            usdc_needed = weth_shortage_float * eth_price * 1.05  # 5%マージン
            usdc_needed_wei = int(usdc_needed * 10 ** 6)

            print(f"🔄 USDC→WETH SWAP実行: {usdc_needed:.2f} USDC → {weth_shortage_float:.6f} WETH")
            print(f"   ETH価格: ${eth_price:.2f}")

            # USDC残高確認
            if usdc_balance >= usdc_needed_wei:
                try:
                    print("🔄 swap_exact_input実行中...")

                    # USDC Approve確認（SwapRouter用）
                    approve_if_needed(USDC_ADDRESS, "0xE592427A0AEce92De3Edee1F18E0157C05861564", usdc_needed_wei)

                    # USDC→WETH SWAP実行
                    swap_result = swap_exact_input(
                        USDC_ADDRESS,  # from_token
                        WETH_ADDRESS,  # to_token
                        usdc_needed_wei,  # amount_in
                        500,  # fee
                        0.25  # slippage (25%)
                    )

                    if swap_result:
                        print("✅ USDC→WETH SWAP成功")

                        # 残高再確認
                        time.sleep(2)
                        weth_balance = get_token_balance(WETH_ADDRESS, wallet.address)
                        print(f"📊 SWAP後WETH残高: {weth_balance / 10 ** 18:.6f}")

                        if weth_balance < amount0_desired:
                            print(f"⚠️ SWAP後も不足: {weth_balance / 10 ** 18:.6f} < {target_weth}")
                            amount0_desired = weth_balance
                            target_weth = weth_balance / 10 ** 18
                            print(f"🔧 投入WETH量を調整: {target_weth:.6f}")
                    else:
                        print("❌ USDC→WETH SWAP失敗")
                        return

                except Exception as e:
                    print(f"❌ SWAP エラー: {e}")
                    return
            else:
                print(f"❌ USDC不足: 必要{usdc_needed:.2f}, 利用可能{usdc_balance / 10 ** 6:.2f}")
                return

    print("=== Step 5.5: USDC不足時の自動SWAP ===")
    # USDC残高チェックと自動SWAP
    usdc_balance = get_token_balance(USDC_ADDRESS, wallet.address)  # 最新残高取得
    if usdc_balance < amount1_desired:
        usdc_shortage = amount1_desired - usdc_balance
        usdc_shortage_float = usdc_shortage / 10 ** 6

        print(f"🔄 USDC不足検知: 不足額 {usdc_shortage_float:.2f} USDC")

        # 🔧 追加: 5 USD閾値チェック
        if usdc_shortage_float < 5.0:
            print(f"💡 不足額が5 USD未満のためSWAP回避: {usdc_shortage_float:.2f} < 5.0")
            print(f"🔧 投入USDC量を実残高に調整: {usdc_balance / 10 ** 6:.2f}")
            amount1_desired = usdc_balance
            target_usdc = usdc_balance / 10 ** 6
            print(f"✅ 調整完了 - SWAP実行せずLP作成続行")
        else:
            print(f"🔄 不足額が5 USD以上のためSWAP実行: {usdc_shortage_float:.2f} >= 5.0")

            # 現在のETH価格取得（簡易計算）
            eth_price = 3900  # フォールバック価格
            try:
                # Pool価格から計算（より正確）
                pool_abi = [
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                            {"internalType": "int24", "name": "tick", "type": "int24"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                pool_contract = w3.eth.contract(address=POOL_ADDRESS, abi=pool_abi)
                slot0 = pool_contract.functions.slot0().call()
                sqrt_price_x96 = slot0[0]
                price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
                eth_price = price_raw * (10 ** 12)  # USDC per WETH
                if eth_price <= 0:
                    eth_price = 3900
            except:
                pass

            # 必要ETH量計算（5%マージン付き）
            eth_needed = (usdc_shortage_float / eth_price) * 1.05
            eth_needed_wei = int(eth_needed * 10 ** 18)
            min_usdc_out = int(usdc_shortage * 0.95)  # 5% slippage

            print(f"🔄 WETH→USDC SWAP実行: {eth_needed:.6f} WETH → {usdc_shortage_float:.2f} USDC")
            print(f"   ETH価格: ${eth_price:.2f}")
            print(f"   最小受取: {min_usdc_out / 10 ** 6:.2f} USDC")

            # WETH残高確認
            weth_balance = get_token_balance(WETH_ADDRESS, wallet.address)

            if weth_balance >= eth_needed_wei:
                # WETH→USDC SWAP実行
                try:
                    print("🔄 swap_exact_input実行中...")

                    # WETH Approve確認（SwapRouter用）
                    approve_if_needed(WETH_ADDRESS, "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                                      eth_needed_wei)  # SwapRouter

                    # swap_exact_input の正しい呼び出し（25%スリッページ使用）
                    swap_result = swap_exact_input(
                        WETH_ADDRESS,  # from_token
                        USDC_ADDRESS,  # to_token
                        eth_needed_wei,  # amount_in
                        500,  # fee
                        0.25  # slippage (25%) - swap_utils.pyのデフォルト値を明示
                    )

                    if swap_result:
                        print("✅ WETH→USDC SWAP成功")

                        # 残高再確認
                        time.sleep(2)  # ブロック確認待機
                        usdc_balance = get_token_balance(USDC_ADDRESS, wallet.address)
                        print(f"📊 SWAP後USDC残高: {usdc_balance / 10 ** 6:.2f}")

                        if usdc_balance < amount1_desired:
                            print(f"⚠️ SWAP後も不足: {usdc_balance / 10 ** 6:.2f} < {target_usdc}")
                            # 不足分を調整
                            amount1_desired = usdc_balance
                            target_usdc = usdc_balance / 10 ** 6
                            print(f"🔧 投入USDC量を調整: {target_usdc:.2f}")

                    else:
                        print("❌ WETH→USDC SWAP失敗")
                        return

                except Exception as e:
                    print(f"❌ SWAP エラー: {e}")
                    return
            else:
                print(f"❌ WETH不足: 必要{eth_needed:.6f}, 利用可能{weth_balance / 10 ** 18:.6f}")
                return
    else:
        print(f"✅ USDC残高十分: {usdc_balance / 10 ** 6:.2f} >= {target_usdc}")

    print("✅ 残高確認完了")

    print("=== Step 6: approve確認 ===")
    # 必要に応じてapprove（無制限approve推奨）
    try:
        approve_if_needed(WETH_ADDRESS, POSITION_MANAGER_ADDRESS, amount0_desired)
        approve_if_needed(USDC_ADDRESS, POSITION_MANAGER_ADDRESS, amount1_desired)
    except Exception as e:
        print(f"❌ approve失敗: {e}")
        return

    print("=== Step 7: LP追加実行 ===")

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

    print("🛡️ 統合版堅牢ガス管理システム開始")

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
        print(f"transaction hash: {result['tx_hash']}")  # main.py対応形式

        # ✅ NFT ID抽出・出力
        print("\n=== 🎯 NFT ID抽出 ===")
        nft_id = extract_nft_id_from_transaction(w3, result['tx_hash'])
        if nft_id:
            print(f"🎯 新NFT ID: {nft_id}")
            print(f"🎯 新NFT ID: {nft_id}")  # rebalance.py検知用（重複出力）
        else:
            print("⚠️ NFT ID抽出失敗")

        print("\n🎉🎉🎉 統合版LP追加成功！ 🎉🎉🎉")
        print("🔄 ETH→WETH自動変換対応")
        print("💰 usable_weth計算対応")
        print("🛡️ 堅牢ガス管理対応")
        print("🎯 NFT ID自動抽出対応")
        print("💡 main.py引数連携対応")
        print("🔄 ETH→USDC自動SWAP対応")
        print("🆕 USDC→WETH自動SWAP対応")
    else:
        print(f"Status: ❌ FAILED")
        print(f"Error: {result['error']}")


def parse_arguments():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(description='Uniswap V3 LP自動化（main.py連携対応版）')

    parser.add_argument('--eth', type=float, help='投入するETH量（例: 0.01）')
    parser.add_argument('--usdc', type=float, help='投入するUSDC量（例: 38.5）')
    parser.add_argument('--auto', action='store_true', help='自動実行モード（ユーザー入力なし）')

    return parser.parse_args()


def main():
    """メイン実行関数（引数対応版）"""
    print("=== 🏆 統合版Uniswap V3 LP自動化（main.py連携対応版 + 自動SWAP復活） ===")
    print("🔄 機能: ETH→WETH自動変換")
    print("💰 機能: usable_weth自動計算")
    print("🛡️ 機能: 堅牢ガス管理")
    print("🎯 機能: NFT ID自動抽出")
    print("💡 新機能: main.py引数連携")
    print("🔄 新機能: ETH→USDC自動SWAP復活")
    print(f"🔧 DEBUG: sys.argv = {sys.argv}")

    # 引数解析
    args = parse_arguments()
    print(f"🔧 DEBUG: parsed args = {args}")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise Exception("Web3接続失敗")

    # ウォレット設定
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("PRIVATE_KEY環境変数が設定されていません")

    wallet = w3.eth.account.from_key(private_key)

    # 実行モード判定
    if args.auto:
        # main.pyからの自動実行
        print(f"\n🤖 main.pyからの自動実行モード")
        if args.eth is not None and args.usdc is not None:
            print(f"💰 カスタム投入額: ETH {args.eth:.6f}, USDC {args.usdc:.2f}")
            robust_lp_mint_test(args.eth, args.usdc)
        else:
            print(f"📋 デフォルト投入額でLP作成")
            robust_lp_mint_test()
    else:
        # 手動実行モード（従来通り）
        if args.eth is not None and args.usdc is not None:
            print(f"\n💰 引数指定モード: ETH {args.eth:.6f}, USDC {args.usdc:.2f}")
            robust_lp_mint_test(args.eth, args.usdc)
        else:
            choice = input(
                "\n実行モードを選択:\n1: 無制限approve設定のみ\n2: 統合版LP追加テスト\n3: 両方実行\n選択 (1/2/3): ")

            if choice == "1":
                # 無制限approve設定のみ（元の関数を使用）
                print("approve設定機能は元のコードを参照してください")
            elif choice == "2":
                # ✅ 統合版LP追加テストのみ
                robust_lp_mint_test()
            elif choice == "3":
                # 両方実行
                print("approve設定 + 統合版LP追加")
                robust_lp_mint_test()
            else:
                print("❌ 無効な選択")


if __name__ == "__main__":
    main()