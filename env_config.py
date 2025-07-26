import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# === RPC/Wallet/GAS設定 ===
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
GAS = int(os.getenv("GAS", "5000000"))
GAS_PRICE = int(os.getenv("GAS_PRICE", "2000000000"))

# === Uniswap V3 SwapRouterアドレス（Arbitrum One公式：固定値） ===
SWAP_ROUTER_ADDRESS = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")

# --- .envからアドレス取得＆チェックサム化 ---
USDC_ADDRESS = Web3.to_checksum_address(os.getenv("USDC_ADDRESS"))
WETH_ADDRESS = Web3.to_checksum_address(os.getenv("WETH_ADDRESS"))

# === swap対象ペア・しきい値・プールfee等をリストで管理 ===
SWAP_PAIRS = [
    {
        "from_symbol": "USDC",
        "from_address": USDC_ADDRESS,    # 例: 0xaf88d065e77c8cc2239327c5edb3a432268e5831
        "to_symbol": "WETH",
        "to_address": WETH_ADDRESS,      # 例: 0x82af49447d8a07e3bd95bd0d56f35241523fbab1
        "threshold": float(os.getenv("SWAP_THRESHOLD_USDC", "10")),   # 10USDC以上でswap発動
        "fee": 500,              # 0.05% pool
        "slippage": float(os.getenv("SLIPPAGE", "1.0")) / 100  # 1.0% → 0.01
    },
    # 例：USDT→ETHも将来追加したい場合
    # {
    #     "from_symbol": "USDT",
    #     "from_address": Web3.to_checksum_address(os.getenv("USDT_ADDRESS")),
    #     "to_symbol": "WETH",
    #     "to_address": WETH_ADDRESS,
    #     "threshold": float(os.getenv("SWAP_THRESHOLD_USDT", "10")),
    #     "fee": 500,
    #     "slippage": float(os.getenv("SLIPPAGE", "1.0")) / 100
    # }
]

# === 従来のLPレンジ系パラメータ（他BOTと併用時用） ===
PAIR = os.getenv("PAIR")
TOKEN0 = os.getenv("TOKEN0")
TOKEN1 = os.getenv("TOKEN1")
GAS_BUFFER_ETH = float(os.getenv("GAS_BUFFER_ETH", "0.01"))
RANGE_WIDTH_PERCENT = float(os.getenv("RANGE_WIDTH_PERCENT", "1.0"))

# 必要ならPOOL_ADDRESSや通知設定もここで管理可
