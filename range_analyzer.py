import json
import logging
from web3 import Web3
from env_config import RPC_URL, RANGE_WIDTH_PERCENT
from decimal import Decimal
from uniswap_utils import get_usdc_eth_prices, price_to_tick

POOL_ADDRESS = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")

def analyze_range():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # USDC/ETH（表示用）、USDC/ETH（Tick用調整済）を取得
    usdc_per_eth_price, usdc_eth_for_tick, tick = get_usdc_eth_prices(w3, POOL_ADDRESS)

    logging.info(f"📊 tick={tick}, price(USDC/ETH)={usdc_per_eth_price:.2f}")

    width = Decimal(str(RANGE_WIDTH_PERCENT)) / Decimal("100")
    lower_price = usdc_per_eth_price * (Decimal("1") - width)
    upper_price = usdc_per_eth_price * (Decimal("1") + width)

    logging.info(f"🔧 target price range: {lower_price:.2f} – {upper_price:.2f}")

    # Tick計算は18桁調整後の価格を使用
    lower_tick = price_to_tick(usdc_eth_for_tick * (Decimal("1") - width))
    upper_tick = price_to_tick(usdc_eth_for_tick * (Decimal("1") + width))

    with open("range_config.json", "w") as f:
        json.dump({
            "lower_tick": lower_tick,
            "upper_tick": upper_tick
        }, f, indent=2)

    logging.info(f"✅ Written tick range: {lower_tick} – {upper_tick}")

if __name__ == "__main__":
    analyze_range()
