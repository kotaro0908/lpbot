# test_add_liquidity.py

from web3 import Web3
from env_config import USDC_ADDRESS, WETH_ADDRESS
import json, os, time

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
GAS_BUFFER_ETH = 0.002   # ネットワーク推奨値に調整

ERC20_ABI = [
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"remaining","type":"uint256"}],"type":"function"},
    {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"success","type":"bool"}],"type":"function"},
]

def check_and_approve_with_verification(token_contract, wallet, spender, amount, w3):
    current_allowance = token_contract.functions.allowance(wallet.address, spender).call()
    balance = token_contract.functions.balanceOf(wallet.address).call()
    print(f"[DEBUG] {token_contract.address} balance: {balance}, allowance: {current_allowance}, need: {amount}")
    if balance < amount:
        raise Exception(f"残高不足: {balance} < {amount}")
    if current_allowance < amount:
        if current_allowance > 0:
            tx = token_contract.functions.approve(spender, 0).build_transaction({
                "from": wallet.address,
                "nonce": w3.eth.get_transaction_count(wallet.address),
                "gas": 80000,
                "gasPrice": w3.to_wei("2", "gwei")
            })
            signed_reset = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
            reset_hash = w3.eth.send_raw_transaction(signed_reset.rawTransaction)
            w3.eth.wait_for_transaction_receipt(reset_hash)
        approve_amount = int(amount * 1.5)
        tx = token_contract.functions.approve(spender, approve_amount).build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": 80000,
            "gasPrice": w3.to_wei("2", "gwei")
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"[INFO] Approve済: {token_contract.address} {approve_amount}")

def get_token_balance(token_contract, address):
    return token_contract.functions.balanceOf(address).call()

def get_eth_balance(w3, address):
    return w3.eth.get_balance(address)

MINT_ABI = [{
    "inputs": [
        {
            "components": [
                {"internalType": "address", "name": "token0", "type": "address"},
                {"internalType": "address", "name": "token1", "type": "address"},
                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                {"internalType": "int24", "name": "tickLower", "type": "int24"},
                {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                {"internalType": "address", "name": "recipient", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "internalType": "struct INonfungiblePositionManager.MintParams",
            "name": "params",
            "type": "tuple"
        }
    ],
    "name": "mint",
    "outputs": [
        {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
        {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
        {"internalType": "uint256", "name": "amount0", "type": "uint256"},
        {"internalType": "uint256", "name": "amount1", "type": "uint256"}
    ],
    "stateMutability": "payable",
    "type": "function"
}]

def add_liquidity(
    w3, wallet, token0, token1, fee, tick_lower, tick_upper,
    amount0_desired, amount1_desired, amount0_min, amount1_min,
    recipient=None, gas=300000, gas_price=None
):
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=MINT_ABI)
    deadline = int(time.time()) + 600
    if recipient is None:
        recipient = wallet.address
    params = (
        token0, token1, fee, tick_lower, tick_upper,
        amount0_desired, amount1_desired,
        amount0_min, amount1_min,
        recipient, deadline
    )
    tx = pm.functions.mint(params).build_transaction({
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
        "gas": gas,
        "gasPrice": gas_price or w3.to_wei("2", "gwei"),
        "value": 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print("[INFO] addLiquidity(mint) tx sent:", w3.to_hex(tx_hash))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

if __name__ == "__main__":
    w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
    wallet = w3.eth.account.from_key(os.getenv("PRIVATE_KEY"))

    token0_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
    token1_contract = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)

    with open("range_config.json") as f:
        cfg = json.load(f)
        tick_lower = cfg["lower_tick"]
        tick_upper = cfg["upper_tick"]

    eth_balance = get_eth_balance(w3, wallet.address)
    weth_balance = get_token_balance(token1_contract, wallet.address)
    usdc_balance = get_token_balance(token0_contract, wallet.address)
    print(f"[現場残高] ETH: {eth_balance/10**18:.6f}, WETH: {weth_balance/10**18:.6f}, USDC: {usdc_balance/10**6:.2f}")

    usable_weth = max((eth_balance + weth_balance)/10**18 - GAS_BUFFER_ETH, 0)
    print(f"[現場usable_weth] {usable_weth:.6f} WETH (ガスバッファ {GAS_BUFFER_ETH}ETH 減算済)")

    price = 3500  # 仮のETH/USDC価格（現場値・自作関数でもOK）
    weth_usd = usable_weth * price
    usdc_usd = usdc_balance / 10**6
    total_usd = weth_usd + usdc_usd
    target_each_usd = total_usd / 2
    print(f"[現場資産(USD)] WETH: {weth_usd:.2f}, USDC: {usdc_usd:.2f}, 合計: {total_usd:.2f} 目標: {target_each_usd:.2f}")

    if weth_usd < usdc_usd:
        amount1_desired = int(0.015 * 10 ** 18)  # 0.015 WETH（現残高内でギリギリ）
        amount0_desired = int((0.015 * 3500) * 10 ** 6)
        amount0_min = int(amount0_desired * 0.98)
        amount1_min = int(amount1_desired * 0.98)
    else:
        amount0_desired = int(usdc_balance)
        amount1_desired = int((usdc_balance / 10**6 / price) * 10**18)
    amount0_min = int(amount0_desired * 0.98)
    amount1_min = int(amount1_desired * 0.98)

    print(f"[投入予定] amount0_desired: {amount0_desired}, amount1_desired: {amount1_desired}")
    print(f"[最低受取] amount0_min: {amount0_min}, amount1_min: {amount1_min}")

    check_and_approve_with_verification(token0_contract, wallet, POSITION_MANAGER_ADDRESS, amount0_desired, w3)
    check_and_approve_with_verification(token1_contract, wallet, POSITION_MANAGER_ADDRESS, amount1_desired, w3)

    receipt = add_liquidity(
        w3, wallet,
        token0=USDC_ADDRESS, token1=WETH_ADDRESS,
        fee=500,
        tick_lower=tick_lower, tick_upper=tick_upper,
        amount0_desired=amount0_desired, amount1_desired=amount1_desired,
        amount0_min=amount0_min, amount1_min=amount1_min,
    )
    print("[RESULT] Mint Tx receipt:")
    print(receipt)
