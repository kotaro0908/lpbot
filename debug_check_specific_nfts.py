#!/usr/bin/env python3
"""
特定NFTの詳細状況確認スクリプト
"""

import os
import json
from web3 import Web3
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# 設定
RPC_URL = os.getenv("RPC_URL")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# Position Manager ABI（必要な関数のみ）
POSITION_MANAGER_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"internalType": "uint96", "name": "nonce", "type": "uint96"},
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "int24", "name": "tickLower", "type": "int24"},
            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
            {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


def check_nft_status(nft_id, w3, position_manager, wallet_address):
    """特定NFTの状況確認"""
    print(f"🔍 NFT {nft_id} 確認:")

    try:
        # 所有者確認
        print(f"   ownerOf({nft_id}) 呼び出し中...")
        owner = position_manager.functions.ownerOf(nft_id).call()
        print(f"   Owner: {owner}")

        if owner.lower() != wallet_address.lower():
            print(f"   ❌ 他の人のNFT（スキップ）")
            return None

        print(f"   ✅ あなたのNFTです")

        # ポジション詳細取得
        print(f"   positions({nft_id}) 呼び出し中...")
        position = position_manager.functions.positions(nft_id).call()

        print(f"   📊 詳細情報:")
        print(f"      Liquidity: {position[7]}")
        print(f"      Range: [{position[5]}, {position[6]}]")
        print(f"      Fee: {position[4]}")
        print(f"      Tokens Owed 0: {position[10]}")
        print(f"      Tokens Owed 1: {position[11]}")

        if position[7] > 0:
            print(f"   🎯 アクティブ（流動性あり）")
            return {
                'token_id': nft_id,
                'liquidity': position[7],
                'tick_lower': position[5],
                'tick_upper': position[6],
                'tokens_owed_0': position[10],
                'tokens_owed_1': position[11]
            }
        else:
            status = "非アクティブ（流動性なし）"
            if position[10] > 0 or position[11] > 0:
                status += f" - 手数料蓄積: {position[10]}, {position[11]}"
            print(f"   📍 {status}")
            return None

    except Exception as e:
        print(f"   ❌ NFT {nft_id} チェックエラー: {e}")
        return None


def main():
    """メイン実行関数"""
    print("=== 🔍 特定NFT状況確認 ===")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Web3接続失敗")
        return

    print("✅ Web3接続成功")
    print(f"Chain ID: {w3.eth.chain_id}")

    # Position Manager契約接続
    position_manager = w3.eth.contract(
        address=POSITION_MANAGER_ADDRESS,
        abi=POSITION_MANAGER_ABI
    )
    print("✅ Position Manager契約接続成功")

    print(f"📍 ウォレット: {WALLET_ADDRESS}")

    # 確認対象NFT（最近のものを含む）
    check_nfts = [4711397, 4711398, 4711399, 4711400, 4711401, 4711402]

    print(f"🎯 確認対象NFT: {check_nfts}")

    active_nfts = []

    for nft_id in check_nfts:
        result = check_nft_status(nft_id, w3, position_manager, WALLET_ADDRESS)
        if result:
            active_nfts.append(result)

    print(f"\n📊 最終結果:")
    if active_nfts:
        print(f"   🎯 アクティブNFT: {len(active_nfts)}個")
        print(f"   📋 詳細:")
        for nft in active_nfts:
            print(f"      NFT {nft['token_id']}: 流動性 {nft['liquidity']}")
            print(f"         レンジ: [{nft['tick_lower']}, {nft['tick_upper']}]")
            if nft['tokens_owed_0'] > 0 or nft['tokens_owed_1'] > 0:
                print(f"         手数料: {nft['tokens_owed_0']}, {nft['tokens_owed_1']}")

        # tracked_nfts.json生成
        active_ids = [nft['token_id'] for nft in active_nfts]
        with open('tracked_nfts.json', 'w') as f:
            json.dump({'nft_ids': active_ids}, f)
        print(f"💾 正しいtracked_nfts.jsonを生成:")
        print(f"   {{'nft_ids': {active_ids}}}")
        print(f"   🚀 これでmain.pyが正しく動作します")
    else:
        print(f"   📍 アクティブなNFTなし")


if __name__ == "__main__":
    main()