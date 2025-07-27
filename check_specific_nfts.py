#!/usr/bin/env python3
import os
import sys
from web3 import Web3
from dotenv import load_dotenv

print("=== 🔍 デバッグ版NFT確認スクリプト開始 ===")

try:
    print("1. dotenv読み込み中...")
    load_dotenv()
    print("   ✅ dotenv読み込み完了")
except Exception as e:
    print(f"   ❌ dotenv読み込みエラー: {e}")
    sys.exit(1)

# 設定
try:
    print("2. 環境変数読み込み中...")
    RPC_URL = os.getenv("RPC_URL")
    print(f"   RPC_URL: {RPC_URL[:50]}..." if RPC_URL else "   ❌ RPC_URL未設定")

    WALLET_ADDRESS = "0xea2Cf9D674A63A0dC49a2F2F080092170Fc052fA"
    POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
    print(f"   WALLET_ADDRESS: {WALLET_ADDRESS}")
    print(f"   POSITION_MANAGER: {POSITION_MANAGER_ADDRESS}")

    if not RPC_URL:
        print("❌ RPC_URL が設定されていません")
        sys.exit(1)

except Exception as e:
    print(f"❌ 設定読み込みエラー: {e}")
    sys.exit(1)

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
    print("\n=== 🔍 特定NFT状況確認 ===")

    try:
        print("3. Web3接続中...")
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        print(f"   Web3オブジェクト作成: {w3}")

        print("4. 接続確認中...")
        if not w3.is_connected():
            print("❌ Web3接続失敗")
            return
        print("   ✅ Web3接続成功")

        # チェーンID確認
        chain_id = w3.eth.chain_id
        print(f"   Chain ID: {chain_id}")

    except Exception as e:
        print(f"❌ Web3接続エラー: {e}")
        return

    try:
        print("5. Position Manager契約接続中...")
        position_manager = w3.eth.contract(
            address=POSITION_MANAGER_ADDRESS,
            abi=POSITION_MANAGER_ABI
        )
        print("   ✅ Position Manager契約接続成功")

    except Exception as e:
        print(f"❌ Position Manager接続エラー: {e}")
        return

    # 確認対象NFT（新しいNFTも追加）
    target_nfts = [4710851, 4711036, 4710975, 4710968, 4710944]

    print(f"\n📍 ウォレット: {WALLET_ADDRESS}")
    print(f"🎯 確認対象NFT: {target_nfts}")

    active_nfts = []

    for nft_id in target_nfts:
        print(f"\n🔍 NFT {nft_id} 確認:")

        try:
            print(f"   ownerOf({nft_id}) 呼び出し中...")
            # オーナー確認
            owner = position_manager.functions.ownerOf(nft_id).call()
            print(f"   Owner: {owner}")

            if owner.lower() == WALLET_ADDRESS.lower():
                print(f"   ✅ あなたのNFTです")

                print(f"   positions({nft_id}) 呼び出し中...")
                # ポジション詳細取得
                position = position_manager.functions.positions(nft_id).call()

                liquidity = position[7]
                tick_lower = position[5]
                tick_upper = position[6]
                tokens_owed_0 = position[10]
                tokens_owed_1 = position[11]

                print(f"   📊 詳細情報:")
                print(f"      Liquidity: {liquidity}")
                print(f"      Range: [{tick_lower}, {tick_upper}]")
                print(f"      Fee: {position[4]}")
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
            import traceback
            traceback.print_exc()

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

        try:
            import json
            with open('tracked_nfts.json', 'w') as f:
                json.dump({'nft_ids': nft_ids}, f)

            print(f"\n💾 正しいtracked_nfts.jsonを生成:")
            print(f"   {{'nft_ids': {nft_ids}}}")
            print(f"   🚀 これでmain.pyが正しく動作します")
        except Exception as e:
            print(f"❌ ファイル書き込みエラー: {e}")

    else:
        print(f"   📍 アクティブなNFTは見つかりませんでした")

    print("\n=== 🔍 デバッグ版NFT確認完了 ===")


if __name__ == "__main__":
    try:
        check_specific_nfts()
    except Exception as e:
        print(f"❌ メイン実行エラー: {e}")
        import traceback

        traceback.print_exc()

    print("スクリプト終了")