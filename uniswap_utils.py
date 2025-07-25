from decimal import Decimal, getcontext
from web3 import Web3

getcontext().prec = 40

# --- プールのslot0取得用ABI ---
SLOT0_ABI = [{
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
}]

# --- PositionManager用の最小ABI ---
POSITION_MANAGER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
        ],
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
            # ...本来はこの後も続くがliquidity取得だけなら省略でOK
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "removeLiquidity",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"  # Arbitrum One

def price_to_tick(price: Decimal) -> int:
    return int((price.ln() / Decimal("1.0001").ln()).to_integral_value(rounding='ROUND_FLOOR'))

def get_usdc_eth_prices(w3: Web3, pool_address: str) -> (Decimal, Decimal, int):
    contract = w3.eth.contract(address=pool_address, abi=SLOT0_ABI)
    slot0 = contract.functions.slot0().call()
    tick = slot0[1]
    sqrtX = slot0[0]

    Q96 = Decimal(2) ** 96
    sqrt_price = Decimal(sqrtX) / Q96
    usdc_per_eth_raw = sqrt_price ** 2

    # 表示用 (3700前後)
    adjusted_usdc_per_eth = usdc_per_eth_raw * (Decimal(10) ** 12)

    # Tick用に18桁に調整 (USDCをETHと同じ桁数に合わせるために必須)
    usdc_per_eth_for_tick = adjusted_usdc_per_eth / (Decimal(10) ** 12)

    return adjusted_usdc_per_eth, usdc_per_eth_for_tick, tick

def add_liquidity(*args, **kwargs):
    pass

def get_liquidity(web3: Web3, token_id: int) -> int:
    """
    Uniswap V3 PositionManagerのpositions(tokenId)からliquidity量を取得
    """
    pm = web3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)
    pos = pm.functions.positions(token_id).call()
    liquidity = pos[7]  # index 7がliquidity
    return liquidity

def remove_liquidity(web3: Web3, wallet, token_id: int, amount0_min: int, amount1_min: int, gas: int, gas_price: int):
    """
    指定tokenIdの全流動性を撤退（removeLiquidity）する
    """
    import time
    pm = web3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)
    liquidity = get_liquidity(web3, token_id)
    deadline = int(time.time()) + 300

    tx = pm.functions.removeLiquidity(
        token_id,
        liquidity,
        amount0_min,
        amount1_min,
        deadline
    ).build_transaction({
        'from': wallet.address,
        'nonce': web3.eth.getTransactionCount(wallet.address),
        'gas': gas,
        'gasPrice': gas_price
    })

    signed_tx = web3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
    print(f"removeLiquidity tx sent: {web3.toHex(tx_hash)}")
    return tx_hash

def collect_fees(*args, **kwargs):
    pass

def get_lp_position(*args, **kwargs):
    return {"token_id": 0}
