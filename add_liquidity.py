# add_liquidity.py - 無制限approve版
from web3 import Web3
from env_config import USDC_ADDRESS, WETH_ADDRESS
import json, os, time
import subprocess

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
RPC_URL = "https://arb1.arbitrum.io/rpc"

# 無制限approve用定数
MAX_UINT256 = 2 ** 256 - 1

# 主要トークン（将来の拡張用）
TOKENS = {
    "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
    "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9"
}

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

POSITION_MANAGER_ABI = [
    {"inputs": [{"components": [{"internalType": "address", "name": "token0", "type": "address"},
                                {"internalType": "address", "name": "token1", "type": "address"},
                                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                                {"internalType": "int24", "name": "tickLower", "type": "int24"},
                                {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                                {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                                {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                                {"internalType": "address", "name": "recipient", "type": "address"},
                                {"internalType": "uint256", "name": "deadline", "type": "uint256"}],
                 "internalType": "struct INonfungiblePositionManager.MintParams", "name": "params", "type": "tuple"}],
     "name": "mint", "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                                 {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                                 {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                                 {"internalType": "uint256", "name": "amount1", "type": "uint256"}],
     "stateMutability": "payable", "type": "function"}
]


def check_unlimited_approve_status(w3, wallet):
    """無制限approve状況の確認"""
    print("=== 🔍 無制限approve状況確認 ===")

    status = {}
    for token_name, token_address in [("WETH", WETH_ADDRESS), ("USDC", USDC_ADDRESS)]:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        allowance = token_contract.functions.allowance(wallet.address, POSITION_MANAGER_ADDRESS).call()

        # 無制限かどうかの判定（MAX_UINT256の50%以上なら無制限とみなす）
        is_unlimited = allowance >= MAX_UINT256 // 2
        status[token_name] = {
            "address": token_address,
            "allowance": allowance,
            "is_unlimited": is_unlimited
        }

        print(f"{token_name}: {'✅ 無制限設定済み' if is_unlimited else '❌ 有限設定'}")
        if not is_unlimited:
            print(f"  現在allowance: {allowance / (10 ** 18 if token_name == 'WETH' else 10 ** 6):.6f}")

    return status


def setup_unlimited_approve(w3, wallet, token_address, token_name):
    """指定トークンの無制限approve設定"""
    print(f"=== 🚀 {token_name} 無制限approve設定 ===")

    try:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)

        # 現在のallowance確認
        current_allowance = token_contract.functions.allowance(
            wallet.address, POSITION_MANAGER_ADDRESS
        ).call()

        if current_allowance >= MAX_UINT256 // 2:
            print(f"✅ {token_name}: 既に無制限設定済み")
            return True

        print(f"🔧 {token_name}: 無制限approve実行中...")

        # 無制限approve実行
        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        approve_tx = token_contract.functions.approve(
            POSITION_MANAGER_ADDRESS,
            MAX_UINT256
        ).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": w3.to_wei("2", "gwei"),
            "value": 0
        })

        signed = wallet.sign_transaction(approve_tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"📝 Approve Tx: {tx_hash.hex()}")

        # 確認待機
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            print(f"✅ {token_name}: 無制限approve完了！")
            print(f"🎉 今後の{token_name}はapprove不要")
            return True
        else:
            print(f"❌ {token_name}: approve失敗")
            return False

    except Exception as e:
        print(f"❌ {token_name} approve実行エラー: {e}")
        return False


def setup_all_unlimited_approves(w3, wallet):
    """全トークンの無制限approve一括設定"""
    print("=== 🏆 Uniswap V3 完全無制限approve設定 ===")
    print("🎯 対象: WETH, USDC")
    print("🚀 効果: 今後のLP操作でapprove問題完全解決")

    success_count = 0

    # 必須トークン（WETH, USDC）
    essential_tokens = [("WETH", WETH_ADDRESS), ("USDC", USDC_ADDRESS)]

    for token_name, token_address in essential_tokens:
        if setup_unlimited_approve(w3, wallet, token_address, token_name):
            success_count += 1

    print(f"\n=== 📊 無制限approve設定結果 ===")
    print(f"成功: {success_count}/{len(essential_tokens)} トークン")

    if success_count == len(essential_tokens):
        print("🎉🎉🎉 完全成功！ 🎉🎉🎉")
        print("✅ WETH: 無制限approve完了")
        print("✅ USDC: 無制限approve完了")
        print("🚀 今後のUniswap V3操作でapprove問題ゼロ！")
        print("📈 利用可能: 全てのETH/USDCプール（全fee tier）")
        return True
    else:
        print("⚠️ 一部失敗 - 再実行を推奨")
        return False


def unlimited_approve_lp_test():
    """無制限approve前提でのLP追加テスト"""
    print("=== 🚀 無制限approve前提 LP追加テスト ===")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise Exception("Web3接続失敗")

    # ウォレット設定
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("PRIVATE_KEY環境変数が設定されていません")

    wallet = w3.eth.account.from_key(private_key)

    print("=== Step 1: レンジ分析実行 ===")
    # range_analyzer.py実行
    result = subprocess.run(
        ["python", "range_analyzer.py"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ レンジ分析失敗: {result.stderr}")
        return

    print("✅ レンジ分析完了")

    print("=== Step 2: レンジ読み込み ===")
    # range_config.json読み込み
    with open("range_config.json", "r") as f:
        range_config = json.load(f)

    tick_lower = range_config["lower_tick"]
    tick_upper = range_config["upper_tick"]

    print(f"使用レンジ: {tick_lower} ～ {tick_upper}")

    print("=== Step 3: 残高確認 ===")
    # 残高確認
    weth_contract = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
    usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)

    weth_balance = weth_contract.functions.balanceOf(wallet.address).call()
    usdc_balance = usdc_contract.functions.balanceOf(wallet.address).call()
    eth_balance = w3.eth.get_balance(wallet.address)

    print(f"残高:")
    print(f"  WETH: {weth_balance / 10 ** 18:.6f}")
    print(f"  USDC: {usdc_balance / 10 ** 6:.2f}")
    print(f"  ETH: {eth_balance / 10 ** 18:.6f}")

    print("=== Step 4: 投入金額設定 ===")
    # 投入金額（小額テスト）
    amount0_desired = int(0.001 * 10 ** 18)  # 0.001 WETH
    amount1_desired = int(3.76 * 10 ** 6)  # 3.76 USDC
    amount0_min = 1  # 最小限
    amount1_min = 1  # 最小限

    print(f"投入予定: {amount0_desired / 10 ** 18:.6f} WETH, {amount1_desired / 10 ** 6:.2f} USDC")

    # 残高チェック
    if weth_balance < amount0_desired or usdc_balance < amount1_desired:
        print(f"❌ 残高不足")
        return

    print("=== Step 5: approve状況確認（無制限前提）===")
    approve_status = check_unlimited_approve_status(w3, wallet)

    # 無制限approve未設定なら設定を提案
    need_setup = False
    for token_name, status in approve_status.items():
        if not status["is_unlimited"]:
            need_setup = True
            break

    if need_setup:
        print("⚠️ 無制限approve未設定のトークンがあります")
        print("🔧 無制限approve設定を実行しますか？")
        response = input("実行する場合は 'yes' を入力: ")

        if response.lower() == 'yes':
            if not setup_all_unlimited_approves(w3, wallet):
                print("❌ 無制限approve設定失敗")
                return
        else:
            print("❌ 無制限approve設定をスキップ - LP追加を中断")
            return
    else:
        print("✅ 全て無制限approve設定済み - approve処理スキップ")

    print("=== Step 6: LP追加実行（approve処理なし）===")
    # Position Manager
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

    # パラメータ準備
    deadline = int(time.time()) + 3600

    params = (
        WETH_ADDRESS,  # token0
        USDC_ADDRESS,  # token1
        500,  # fee
        tick_lower,  # tickLower
        tick_upper,  # tickUpper
        amount0_desired,  # amount0Desired
        amount1_desired,  # amount1Desired
        amount0_min,  # amount0Min
        amount1_min,  # amount1Min
        wallet.address,  # recipient
        deadline  # deadline
    )

    print(f"🚀 LP追加実行（approve処理なし）")

    # トランザクション構築
    nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

    tx_data = pm.functions.mint(params).build_transaction({
        "from": wallet.address,
        "nonce": nonce,
        "gas": 600000,  # 成功実績ベース
        "gasPrice": w3.to_wei("2", "gwei"),
        "value": 0
    })

    # 署名・送信
    signed = wallet.sign_transaction(tx_data)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

    print(f"🚀 LP Mint Tx: {tx_hash.hex()}")

    # 結果確認
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        print("=== 📊 実行結果 ===")
        print(f"Status: {'✅ SUCCESS' if receipt.status == 1 else '❌ FAILED'}")
        print(f"Gas Used: {receipt.gasUsed:,}")
        print(f"Events: {len(receipt.logs)} 個")
        print(f"Tx Hash: {tx_hash.hex()}")

        if receipt.status == 1:
            print("🎉🎉🎉 無制限approve版 LP追加成功！ 🎉🎉🎉")
            print("✨ approve問題完全解決")
            print("🚀 今後のLP操作は超高速・確実")
        else:
            print("💀 LP追加失敗 - Arbiscanで詳細確認")

    except Exception as e:
        print(f"❌ トランザクション確認エラー: {e}")


def main():
    """メイン実行関数"""
    print("=== 🏆 Uniswap V3 無制限approve版 LP自動化 ===")
    print("🎯 目標: approve問題の完全解決")
    print("🚀 効果: LP操作の超高速・確実化")

    choice = input("\n実行モードを選択:\n1: 無制限approve設定のみ\n2: LP追加テスト\n3: 両方実行\n選択 (1/2/3): ")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise Exception("Web3接続失敗")

    # ウォレット設定
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("PRIVATE_KEY環境変数が設定されていません")

    wallet = w3.eth.account.from_key(private_key)

    if choice == "1":
        # 無制限approve設定のみ
        setup_all_unlimited_approves(w3, wallet)
    elif choice == "2":
        # LP追加テストのみ
        unlimited_approve_lp_test()
    elif choice == "3":
        # 両方実行
        if setup_all_unlimited_approves(w3, wallet):
            print("\n" + "=" * 50)
            unlimited_approve_lp_test()
    else:
        print("❌ 無効な選択")


if __name__ == "__main__":
    main()