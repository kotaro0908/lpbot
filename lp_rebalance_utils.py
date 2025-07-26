from uniswap_utils import get_eth_usdc_price
from swap_utils import get_token_balance, swap_exact_input, approve_if_needed
from env_config import WETH_ADDRESS, USDC_ADDRESS, REBALANCE_THRESHOLD_USD
from web3 import Web3
import os

def check_allowance(w3, token_address, owner, spender):
    ERC20_ABI = [
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"}
            ],
            "name": "allowance",
            "outputs": [{"name": "remaining", "type": "uint256"}],
            "type": "function"
        }
    ]
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return token.functions.allowance(owner, spender).call()

def wrap_eth_to_weth(w3, wallet, amount_wei):
    weth_abi = [{"inputs": [], "name": "deposit", "outputs": [], "stateMutability": "payable", "type": "function"}]
    weth = w3.eth.contract(address=WETH_ADDRESS, abi=weth_abi)
    tx = weth.functions.deposit().build_transaction({
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
        "value": int(amount_wei),
        "gas": 100000,
        "gasPrice": w3.to_wei("2", "gwei"),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"[INFO] wrap ETH→WETH: {w3.to_hex(tx_hash)}")
    w3.eth.wait_for_transaction_receipt(tx_hash)

def get_lp_balances(w3, wallet):
    weth_balance = get_token_balance(WETH_ADDRESS, wallet.address)
    usdc_balance = get_token_balance(USDC_ADDRESS, wallet.address)
    eth_balance = w3.eth.get_balance(wallet.address)
    return weth_balance, usdc_balance, eth_balance

def rebalance_and_provide_liquidity(w3, wallet, pool_address, min_lp_unit_usd=10):
    GAS_BUFFER_ETH = float(os.getenv("GAS_BUFFER_ETH", "0.01"))
    price = get_eth_usdc_price(w3, pool_address)
    weth_balance, usdc_balance, eth_balance = get_lp_balances(w3, wallet)

    # usable_wethはガスバッファ差引後
    total_weth = (weth_balance + eth_balance) / 10 ** 18
    usable_weth = max(total_weth - GAS_BUFFER_ETH, 0)
    weth_usd = usable_weth * price
    usdc_usd = usdc_balance / 10 ** 6

    total_assets_usd = weth_usd + usdc_usd
    target_each_usd = total_assets_usd / 2

    print(f"[DEBUG] ETH: {eth_balance / 10**18} | WETH: {weth_balance / 10**18} | USDC: {usdc_balance / 10**6}")
    print(f"[DEBUG] usable_weth: {usable_weth} | WETH(USD): {weth_usd} | USDC(USD): {usdc_usd} | 合計: {total_assets_usd}USD | 目標: {target_each_usd}USDずつ")

    router_address = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")

    # 目標に合わせて一発リバランスswap
    swap_needed = target_each_usd - weth_usd  # swap_needed>0ならUSDC→WETH, <0ならWETH→USDC
    print(f"[DEBUG] swap_needed: {swap_needed} USD")

    if abs(swap_needed) >= REBALANCE_THRESHOLD_USD:
        try:
            if swap_needed > 0:
                # USDC→WETH swap
                swap_amount = swap_needed * 10**6
                approve_if_needed(USDC_ADDRESS, router_address, int(swap_amount))
                print(f"[INFO] USDC→WETH swap: {swap_needed}USD（{swap_amount/10**6} USDC）")
                swap_exact_input(USDC_ADDRESS, WETH_ADDRESS, int(swap_amount))
            else:
                # WETH→USDC swap
                swap_amount = (-swap_needed / price) * 10**18
                # wrap不足ならETH→WETHで補充
                wrap_needed = max(swap_amount - weth_balance, 0)
                if wrap_needed > 0 and eth_balance >= wrap_needed:
                    print(f"[INFO] wrap不足分ETH→WETH: {wrap_needed/10**18}ETH")
                    wrap_eth_to_weth(w3, wallet, int(wrap_needed))
                approve_if_needed(WETH_ADDRESS, router_address, int(swap_amount))
                print(f"[INFO] WETH→USDC swap: {-swap_needed}USD（{swap_amount/10**18} WETH）")
                swap_exact_input(WETH_ADDRESS, USDC_ADDRESS, int(swap_amount))
        except Exception as e:
            print(f"[ERROR] リバランスswap/wrap失敗: {e}")
            return
        # swap後、再取得
        weth_balance, usdc_balance, eth_balance = get_lp_balances(w3, wallet)
        total_weth = (weth_balance + eth_balance) / 10 ** 18
        usable_weth = max(total_weth - GAS_BUFFER_ETH, 0)
        weth_usd = usable_weth * price
        usdc_usd = usdc_balance / 10 ** 6
        total_assets_usd = weth_usd + usdc_usd
        target_each_usd = total_assets_usd / 2

    min_usd = min(weth_usd, usdc_usd)
    if min_usd < min_lp_unit_usd:
        print(f"[SKIP] どちらかの資金がLP最小投入単位({min_lp_unit_usd}USD)未満。LP不可")
        return

    print(f"[READY] LP投入: {min_usd} USD相当ずつでペア組成（実装例）")
    # add_liquidity(w3, wallet, pool_address, 必要amount0, amount1, etc)を呼ぶ

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    RPC_URL = os.getenv("RPC_URL")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    wallet = w3.eth.account.from_key(PRIVATE_KEY)
    pool_address = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")
    rebalance_and_provide_liquidity(w3, wallet, pool_address, min_lp_unit_usd=10)
