import os
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# トークンペアと閾値を辞書で管理
SWAP_PAIRS = [
    {
        "from_symbol": "USDC",
        "from_address": os.getenv("USDC_ADDRESS"),
        "to_symbol": "ETH",
        "to_address": os.getenv("WETH_ADDRESS"),
        "threshold": float(os.getenv("SWAP_THRESHOLD_USDC", "10"))
    },
    # 将来追加ペアもここに増やすだけ
    # {
    #     "from_symbol": "USDT",
    #     "from_address": os.getenv("USDT_ADDRESS"),
    #     "to_symbol": "ETH",
    #     "to_address": os.getenv("WETH_ADDRESS"),
    #     "threshold": float(os.getenv("SWAP_THRESHOLD_USDT", "10"))
    # },
]
SWAP_ROUTER_ADDRESS = os.getenv("SWAP_ROUTER_ADDRESS")  # Uniswap V3 SwapRouter
