import asyncio, logging
from web3 import Web3
from env_config import RPC_URL
from range_checker import check_range

POOL_ADDRESS = Web3.to_checksum_address("0xc6962004f452bE9203591991D15f6b388e09e8d0")
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

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

async def monitor_slot0():
    logging.info(f"🔌 Connecting to {RPC_URL}")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        logging.error("❌ Web3 未接続")
        return
    logging.info(f"✅ chain_id={w3.eth.chain_id}")
    if not w3.eth.get_code(POOL_ADDRESS):
        logging.error("❌ 指定プールが存在しません")
        return
    logging.info("✅ Pool contract exists")

    c = w3.eth.contract(address=POOL_ADDRESS, abi=SLOT0_ABI)
    while True:
        try:
            slot0 = c.functions.slot0().call()
            tick, sqrtX = slot0[1], slot0[0]
            logging.info(f"📊 tick={tick}, sqrtX96={sqrtX}")
            in_range = not check_range(tick)
            logging.info("🔶 レンジ内 → 維持" if in_range else "🔵 レンジ外 → 再構築")
        except Exception as e:
            logging.error("❌ slot0 取得エラー:", exc_info=e)
        await asyncio.sleep(30)

if __name__=="__main__":
    asyncio.run(monitor_slot0())
