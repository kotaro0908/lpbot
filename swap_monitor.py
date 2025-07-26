from env_config import SWAP_PAIRS, SWAP_ROUTER_ADDRESS
from swap_utils import w3, wallet, get_token_balance, get_token_decimals, approve_if_needed, swap_exact_input
import time

def main_loop():
    print("=== Swap自動化モニター起動（Arbitrum対応・デバッグ付き）===")
    while True:
        for pair in SWAP_PAIRS:
            from_address = pair["from_address"]
            to_address = pair["to_address"]
            threshold = pair["threshold"]
            fee = pair.get("fee", 500)
            slippage = pair.get("slippage", 0.01)
            decimals = get_token_decimals(from_address)
            balance = get_token_balance(from_address, wallet.address)
            balance_human = balance / (10 ** decimals)

            # === デバッグ出力 ===
            print(f"[DEBUG] wallet.address: {wallet.address}")
            print(f"[DEBUG] from_address: {from_address}")
            print(f"[DEBUG] USDC balance raw: {balance}")
            print(f"[DEBUG] decimals: {decimals}")
            print(f"[CHECK] {pair['from_symbol']} 残高: {balance_human}（しきい値: {threshold}）")

            threshold_wei = int(threshold * (10 ** decimals))
            if balance >= threshold_wei:
                print(f"[TRIGGER] {pair['from_symbol']} 残高がしきい値超過 → approve & swap 実行")
                approve_if_needed(from_address, SWAP_ROUTER_ADDRESS, balance)
                swap_exact_input(from_address, to_address, balance, fee=fee, slippage=slippage)
            else:
                print(f"[PASS] {pair['from_symbol']} 残高がしきい値未満（スキップ）")
        print("[LOOP] 60秒スリープ...")
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
