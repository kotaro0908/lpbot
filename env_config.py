import os
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PAIR = os.getenv("PAIR")
SLIPPAGE = float(os.getenv("SLIPPAGE", "1.0"))
GAS_BUFFER_ETH = float(os.getenv("GAS_BUFFER_ETH", "0.01"))
RANGE_WIDTH_PERCENT = float(os.getenv("RANGE_WIDTH_PERCENT", "1.0"))  # ← ⭐️ ここをfloatに！
