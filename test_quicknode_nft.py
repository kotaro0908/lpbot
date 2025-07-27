#!/usr/bin/env python3
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# 設定
RPC_URL = os.getenv("RPC_URL")
WALLET_ADDRESS = "0xea2Cf9D674A63A0dC49a2F2F080092170Fc052fA"
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# Position Manager ABI
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


def check_specific_nfts():
    print("=== 🔍 特定NFT状況確認 ===")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Web3接続失敗")
        return

    # Position Manager接続
    position_manager = w3.eth.contract(
        address=POSITION_MANAGER_ADDRESS,
        abi=POSITION_MANAGER_ABI
    )

    # 確認対象NFT
    target_nfts = [4710851, 4710975, 4710968, 4710944]

    print(f"📍 ウォレット: {WALLET_ADDRESS}")
    print(f"🎯 確認対象NFT: {target_nfts}")

    active_nfts = []

    for nft_id in target_nfts:
        print(f"\n🔍 NFT {nft_id} 確認:")

        try:
            # オーナー確認
            owner = position_manager.functions.ownerOf(nft_id).call()
            print(f"   Owner: {owner}")

            if owner.lower() == WALLET_ADDRESS.lower():
                print(f"   ✅ あなたのNFTです")

                # ポジション詳細取得
                position = position_manager.functions.positions(nft_id).call()

                nonce = position[0]
                operator = position[1]
                token0 = position[2]
                token1 = position[3]
                fee = position[4]
                tick_lower = position[5]
                tick_upper = position[6]
                liquidity = position[7]
                fee_growth_0 = position[8]
                fee_growth_1 = position[9]
                tokens_owed_0 = position[10]
                tokens_owed_1 = position[11]

                print(f"   📊 詳細情報:")
                print(f"      Liquidity: {liquidity}")
                print(f"      Range: [{tick_lower}, {tick_upper}]")
                print(f"      Fee: {fee}")
                print(f"      Tokens Owed 0: {tokens_owed_0}")
                print(f"      Tokens Owed 1: {tokens_owed_1}")

                if liquidity > 0:
                    print(f"   🎯 アクティブ（流動性あり）")
                    active_nfts.append({
                        'token_id': nft_id,
                        'liquidity': liquidity,
                        'tick_lower': tick_lower,
                        'tick_upper': tick_upper,
                        'tokens_owed_0': tokens_owed_0,
                        'tokens_owed_1': tokens_owed_1
                    })
                else:
                    print(f"   📍 非アクティブ（流動性なし）")
                    if tokens_owed_0 > 0 or tokens_owed_1 > 0:
                        print(f"   💰 手数料蓄積あり（回収可能）")

            else:
                print(f"   ❌ 他の人のNFT（Owner: {owner[:10]}...）")

        except Exception as e:
            print(f"   ❌ エラー: {e}")

    print(f"\n📊 最終結果:")
    print(f"   🎯 アクティブNFT: {len(active_nfts)}個")

    if active_nfts:
        print(f"   📋 詳細:")
        for nft in active_nfts:
            print(f"      NFT {nft['token_id']}: 流動性 {nft['liquidity']}")
            print(f"         レンジ: [{nft['tick_lower']}, {nft['tick_upper']}]")
            if nft['tokens_owed_0'] > 0 or nft['tokens_owed_1'] > 0:
                print(f"         💰 蓄積手数料: {nft['tokens_owed_0']}, {nft['tokens_owed_1']}")

        # 正しいtracked_nfts.jsonを生成
        nft_ids = [nft['token_id'] for nft in active_nfts]

        import json
        with open('tracked_nfts.json', 'w') as f:
            json.dump({'nft_ids': nft_ids}, f)

        print(f"\n💾 正しいtracked_nfts.jsonを生成:")
        print(f"   {{'nft_ids': {nft_ids}}}")
        print(f"   🚀 これでmain.pyが正しく動作します")

    else:
        print(f"   📍 アクティブなNFTは見つかりませんでした")


if __name__ == "__main__":
    check_specific_nfts()