# simple_lp_test.py - 最小テスト版
print("=== 🔄 LP Manager 最小テスト ===")

try:
    print("1. 基本import確認...")
    import os
    import json
    import time

    print("✅ 基本import成功")

    print("2. Web3 import確認...")
    from web3 import Web3

    print("✅ Web3 import成功")

    print("3. 環境変数確認...")
    private_key = os.getenv("PRIVATE_KEY")
    if private_key:
        print("✅ PRIVATE_KEY設定済み")
    else:
        print("❌ PRIVATE_KEY未設定")
        print("解決方法: source .env")
        exit(1)

    print("4. Web3接続確認...")
    RPC_URL = "https://arb1.arbitrum.io/rpc"
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if w3.is_connected():
        print(f"✅ Web3接続成功 (ブロック: {w3.eth.block_number})")
    else:
        print("❌ Web3接続失敗")
        exit(1)

    print("5. ウォレット設定確認...")
    wallet = w3.eth.account.from_key(private_key)
    print(f"✅ ウォレット設定成功")
    print(f"   アドレス: {wallet.address}")

    eth_balance = w3.eth.get_balance(wallet.address)
    print(f"   ETH残高: {eth_balance / 10 ** 18:.6f} ETH")

    print("6. プール接続確認...")
    pool_address = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
    pool_abi = [
        {"inputs": [], "name": "slot0",
         "outputs": [{"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                     {"internalType": "int24", "name": "tick", "type": "int24"},
                     {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                     {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                     {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                     {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                     {"internalType": "bool", "name": "unlocked", "type": "bool"}], "stateMutability": "view",
         "type": "function"}
    ]

    pool_contract = w3.eth.contract(address=pool_address, abi=pool_abi)
    slot0 = pool_contract.functions.slot0().call()
    current_tick = slot0[1]
    print(f"✅ プール接続成功 (現在tick: {current_tick})")

    print("\n🎉 全ての基本機能が正常です！")
    print("lp_manager.pyの実行準備完了")

except Exception as e:
    print(f"❌ エラー発生: {e}")
    import traceback

    traceback.print_exc()