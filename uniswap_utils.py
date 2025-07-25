from decimal import Decimal, getcontext
from web3 import Web3

getcontext().prec = 40

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

def remove_liquidity(web3, wallet, token_id):
    """
    Uniswap V3のNFTポジションをremove（流動性撤退）する関数
    ※ ABIやコントラクトアドレスは別途管理
    """
    # ここでweb3経由でUniswap V3 PositionManagerのremoveLiquidityをコール
    pass  # 詳細は順次肉付け

def collect_fees(*args, **kwargs):
    pass

def get_lp_position(*args, **kwargs):
    return {"token_id": 0}
