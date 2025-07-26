# test_remove.py

import os
from web3 import Web3
from dotenv import load_dotenv
from uniswap_utils import get_liquidity, decrease_liquidity, collect_fees

load_dotenv()
RPC_URL      = os.getenv('RPC_URL')
PRIVATE_KEY  = os.getenv('PRIVATE_KEY')
GAS          = int(os.getenv('GAS', 5000000))
GAS_PRICE    = int(os.getenv('GAS_PRICE', 2000000000))
TOKEN_ID     = int(os.getenv('TOKEN_ID', 4707661))  # テストNFTのtokenId

w3     = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.eth.account.from_key(PRIVATE_KEY)

liquidity = get_liquidity(w3, TOKEN_ID)
print(f"[INFO] liquidity for tokenId {TOKEN_ID}: {liquidity}")

WITHDRAW_PCT = 1.0
liquidity_to_remove = int(liquidity * WITHDRAW_PCT)
print(f"[INFO] removing liquidity: {liquidity_to_remove}")

# === Uniswap UIで撤退時の受取予定額を確認 ===
expected_amount0 = 0.006    # ETH側（例：UIで表示されたWETH数量）
expected_amount1 = 29.31    # USDC側（例：UIで表示されたUSDC数量）

BUFFER = 0.05  # 5%バッファ

AMOUNT0_MIN = int(expected_amount0 * (1 - BUFFER) * 10**18)  # ETH最小受取（18桁wei）
AMOUNT1_MIN = int(expected_amount1 * (1 - BUFFER) * 10**6)   # USDC最小受取（6桁）

print(f"[INFO] AMOUNT0_MIN (ETH最小受取wei): {AMOUNT0_MIN}")
print(f"[INFO] AMOUNT1_MIN (USDC最小受取6桁): {AMOUNT1_MIN}")

def safe_collect():
    """collectのnonceずれ・二重送信対策。何度でも実行OKな構成"""
    try:
        # 最新nonceで送信（状態変化後に確実に回収できるように）
        tx_hash2 = collect_fees(
            w3,
            wallet,
            TOKEN_ID,
            GAS,
            GAS_PRICE
        )
        print(f"[INFO] collect sent: {w3.to_hex(tx_hash2)}")
        receipt2 = w3.eth.wait_for_transaction_receipt(tx_hash2)
        if receipt2.status == 1:
            print(f"[SUCCESS] collect Tx confirmed in block: {receipt2.blockNumber}")
        else:
            print("[ERROR] collect Tx failed at block level。未回収残高があるかも")
    except Exception as e:
        # 既にfee回収済み/残高なしならこのエラーもOK
        if "already been used" in str(e) or "revert" in str(e):
            print("[WARN] collect Tx: 既にfee回収済み、または残高なしの可能性")
        else:
            print(f"[ERROR] collect Tx exception: {e}")

if liquidity_to_remove > 0:
    # decreaseLiquidity送信
    try:
        tx_hash = decrease_liquidity(
            w3,
            wallet,
            TOKEN_ID,
            liquidity_to_remove,
            AMOUNT0_MIN,
            AMOUNT1_MIN,
            GAS,
            GAS_PRICE
        )
        print(f"[INFO] decreaseLiquidity sent: {w3.to_hex(tx_hash)}")
        # ブロック反映まで待機
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            print(f"[SUCCESS] decreaseLiquidity Tx confirmed in block: {receipt.blockNumber}")
        else:
            print("[ERROR] decreaseLiquidity Tx failed at block level.")
            exit(1)
    except Exception as e:
        print(f"[ERROR] decreaseLiquidity Tx exception: {e}")
        exit(1)

    # collect送信（decreaseLiquidityのTxが確定してから！）
    safe_collect()

else:
    print(f"[WARN] liquidity is already 0. 撤退不要")
