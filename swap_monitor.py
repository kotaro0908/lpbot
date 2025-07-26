for pair in SWAP_PAIRS:
    balance = get_token_balance(pair["from_address"], wallet.address)
    decimals = 6 if pair["from_symbol"] == "USDC" else 18  # 例：USDC6桁, ETH18桁
    threshold_wei = int(pair["threshold"] * (10 ** decimals))
    if balance >= threshold_wei:
        print(f"[INFO] {pair['from_symbol']} 残高 {balance / (10 ** decimals)} 超過→swap実行")
        approve_if_needed(pair["from_address"], SWAP_ROUTER_ADDRESS, balance)
        swap_exact_input(pair["from_address"], pair["to_address"], balance)
    else:
        print(f"[INFO] {pair['from_symbol']} 残高 {balance / (10 ** decimals)} < 閾値 {pair['threshold']} →swapしない")
