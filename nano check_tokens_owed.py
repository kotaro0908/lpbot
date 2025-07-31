from web3 import Web3
import json

# ---------- 設定 ----------
INFURA_URL = "https://convincing-rough-energy.arbitrum-mainnet.quiknode.pro/6e3af6701aadae6bf19ccaf7e0b4f99eec4e3297/"
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# ABI（部分抜粋でOK）
POSITION_MANAGER_ABI = [
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

# ---------- 初期化 ----------
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

# ---------- チェックしたいNFT ID一覧 ----------
nft_ids = [
    4723835, 4723879, 4723947, 4724020, 4724059, 4724477, 4724616, 4724698,
    4724769, 4724812, 4724874, 4725068, 4725100, 4725231, 4725479, 4725614,
    4725672, 4725832, 4725854, 4725893, 4725935, 4725955, 4726165, 4726446,
    4726471, 4726560, 4726587, 4726651, 4726713, 4726752, 4726809, 4726918,
    4726964, 4726984, 4727088, 4727185, 4727328, 4727392, 4727548, 4727599,
    4727728, 4727775, 4727804
]

# ---------- チェック処理 ----------
print("🔍 未回収（tokensOwed > 0）NFT一覧:")
for nft_id in nft_ids:
    try:
        pos = pm.functions.positions(nft_id).call()
        owed0 = pos[10] / 10**18   # token0（通常WETH）
        owed1 = pos[11] / 10**6    # token1（通常USDC）

        if owed0 > 0 or owed1 > 0:
            print(f"🟥 NFT {nft_id} → Owed0 (WETH): {owed0:.6f}, Owed1 (USDC): {owed1:.2f}")

    except Exception as e:
        print(f"⚠️  NFT {nft_id} → エラー: {str(e)}")
