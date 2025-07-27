import json
import logging
from web3 import Web3
from env_config import RPC_URL, RANGE_WIDTH_PERCENT

POOL_ADDRESS = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")


def get_current_tick_directly(w3, pool_address):
    """プールから直接現在tickを取得"""
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

    pool = w3.eth.contract(address=pool_address, abi=SLOT0_ABI)
    slot0 = pool.functions.slot0().call()
    current_tick = slot0[1]
    sqrt_price_x96 = slot0[0]

    # 価格計算（USDC/ETH）
    price = (sqrt_price_x96 ** 2 * (10 ** 12)) / (2 ** 192)

    return current_tick, price


def analyze_range():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # 直接現在tickを取得
    current_tick, usdc_per_eth_price = get_current_tick_directly(w3, POOL_ADDRESS)

    logging.info(f"🎯 現場tick（直接取得）: {current_tick}")
    logging.info(f"📊 現場価格(USDC/ETH): {usdc_per_eth_price:.2f}")

    # 現在tickから直接±幅でレンジ計算
    # 1% ≈ 約100tick、2% ≈ 約200tick（目安）
    width_percent = float(RANGE_WIDTH_PERCENT)
    tick_width = int(width_percent * 100)  # 1%=100tick目安

    lower_tick = current_tick - tick_width
    upper_tick = current_tick + tick_width

    # fee=500の場合、tick_spacingは10なので10の倍数に調整
    tick_spacing = 10
    lower_tick = (lower_tick // tick_spacing) * tick_spacing
    upper_tick = (upper_tick // tick_spacing) * tick_spacing

    logging.info(f"🔧 幅設定: ±{width_percent}% (約±{tick_width}tick)")
    logging.info(f"📏 調整後tick範囲: {lower_tick} ～ {upper_tick}")

    # 現在tickがレンジ内かチェック
    if lower_tick <= current_tick <= upper_tick:
        logging.info("✅ 現在tickはレンジ内です")
    else:
        logging.info("❌ 現在tickがレンジ外です（計算エラー）")

    with open("range_config.json", "w") as f:
        json.dump({
            "lower_tick": lower_tick,
            "upper_tick": upper_tick
        }, f, indent=2)

    logging.info(f"✅ range_config.json更新完了: {lower_tick} ～ {upper_tick}")


if __name__ == "__main__":
    analyze_range()