import os
import time
from web3 import Web3
from env_config import RPC_URL, PRIVATE_KEY, SWAP_ROUTER_ADDRESS

# --- 必要なABI ---
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]


def get_token_balance(token_address, wallet_address):
    """トークン残高取得"""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return token_contract.functions.balanceOf(wallet_address).call()


def approve_if_needed(token_address, spender_address, amount):
    """必要に応じてapprove実行"""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("[ERROR] PRIVATE_KEY not found")
        return False

    wallet = w3.eth.account.from_key(private_key)
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

    # 現在のallowance確認
    current_allowance = token_contract.functions.allowance(wallet.address, spender_address).call()

    if current_allowance >= amount:
        print(f"[INFO] already approved: allowance={current_allowance}")
        return True

    # approve実行
    try:
        # 無制限approve（推奨）
        max_uint256 = 2 ** 256 - 1

        tx = token_contract.functions.approve(spender_address, max_uint256).build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": 100000,
            "gasPrice": w3.to_wei("2", "gwei")
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"[INFO] approve sent: {tx_hash.hex()}")

        # トランザクション確認
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            print(f"[INFO] approve success")
            return True
        else:
            print(f"[ERROR] approve failed")
            return False

    except Exception as e:
        print(f"[ERROR] approve exception: {e}")
        return False


def swap_exact_input(token_in, token_out, amount_in, fee=500, slippage=0.25):
    """
    ETH→USDC等のSWAP実行（戻り値対応版）

    Args:
        token_in: 入力トークンアドレス
        token_out: 出力トークンアドレス
        amount_in: 入力量（wei）
        fee: プールフィー（500 = 0.05%）
        slippage: スリッページ許容率（0.25 = 25%、小額SWAP用）

    Returns:
        bool: True=成功, False=失敗
    """
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))

        if not w3.is_connected():
            print("[ERROR] Web3 connection failed")
            return False

        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            print("[ERROR] PRIVATE_KEY not found")
            return False

        wallet = w3.eth.account.from_key(private_key)

        # SwapRouterコントラクト
        swap_router = w3.eth.contract(address=SWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI)

        # approve確認（SwapRouter用）
        if not approve_if_needed(token_in, SWAP_ROUTER_ADDRESS, amount_in):
            print("[ERROR] approve failed for SwapRouter")
            return False

        # 🔧 修正: より現実的なamountOutMinimum計算
        if token_in.lower() == "0x82af49447d8a07e3bd95bd0d56f35241523fbab1":  # WETH
            # ETH→USDC: 保守的計算
            estimated_usdc_out = (amount_in / 10**18) * 3800 * 10**6  # 保守的ETH価格
            amount_out_minimum = int(estimated_usdc_out * (1 - slippage))
        else:
            # その他: 従来計算（改善）
            amount_out_minimum = int(amount_in * (1 - slippage) * 0.01)  # 0.001 → 0.01

        # SWAP パラメータ
        deadline = int(time.time()) + 3600  # 1時間後

        params = (
            token_in,  # tokenIn
            token_out,  # tokenOut
            fee,  # fee
            wallet.address,  # recipient
            deadline,  # deadline
            amount_in,  # amountIn
            amount_out_minimum,  # amountOutMinimum
            0  # sqrtPriceLimitX96 (0 = no limit)
        )

        # ガス見積もり
        try:
            gas_estimate = swap_router.functions.exactInputSingle(params).estimate_gas({
                "from": wallet.address,
                "value": 0
            })
            gas_limit = int(gas_estimate * 1.3)  # 20% → 30%マージン
        except Exception as e:
            print(f"[WARNING] gas estimate failed: {e}")
            gas_limit = 400000  # 300000 → 400000

        # トランザクション構築
        tx = swap_router.functions.exactInputSingle(params).build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": gas_limit,
            "gasPrice": w3.to_wei("3", "gwei"),  # 2 → 3 gwei
            "value": 0
        })

        # 署名・送信
        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        print(f"[INFO] swap sent: {tx_hash.hex()}")

        # トランザクション確認
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)  # 120 → 180秒

        if receipt.status == 1:
            print(f"[INFO] swap success: {tx_hash.hex()}")
            print(f"[INFO] gas used: {receipt.gasUsed:,}")
            return True
        else:
            print(f"[ERROR] swap failed: {tx_hash.hex()}")
            return False

    except Exception as e:
        print(f"[ERROR] swap exception: {e}")
        return False


# テスト用メイン関数
if __name__ == "__main__":
    # テスト実行
    print("=== swap_utils.py テスト ===")

    # 残高確認テスト
    from env_config import USDC_ADDRESS, WETH_ADDRESS

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    wallet = w3.eth.account.from_key(os.getenv("PRIVATE_KEY"))

    eth_balance = w3.eth.get_balance(wallet.address)
    weth_balance = get_token_balance(WETH_ADDRESS, wallet.address)
    usdc_balance = get_token_balance(USDC_ADDRESS, wallet.address)

    print(f"ETH: {eth_balance / 10 ** 18:.6f}")
    print(f"WETH: {weth_balance / 10 ** 18:.6f}")
    print(f"USDC: {usdc_balance / 10 ** 6:.2f}")

    print("\n✅ swap_utils.py テスト完了")