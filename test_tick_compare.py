#testtest

import json
from web3 import Web3
from env_config import RPC_URL
from uniswap_utils import get_usdc_eth_prices

POOL_ADDRESS = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# 1. range_config.jsonのtickを読む
with open("range_config.json") as f:
    cfg = json.load(f)
    lower_tick = cfg["lower_tick"]
    upper_tick = cfg["upper_tick"]
print(f"range_config.json: lower_tick={lower_tick}, upper_tick={upper_tick}")

# 2. 現場tick取得（Uniswapプールからオンチェーン値取得）
usdc_per_eth_price, eth_per_usdc_price, current_tick = get_usdc_eth_prices(w3, POOL_ADDRESS)
print(f"現場tick: {current_tick}")
print(f"現場価格（USDC/ETH）: {usdc_per_eth_price}")

# 3. レンジ内かどうか判定
if lower_tick <= current_tick <= upper_tick:
    print("✅ 現tickはレンジ内です")
else:
    print("❌ 現tickはレンジ外です")
