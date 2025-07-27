#!/usr/bin/env python3
"""
Uniswap V3 ユーティリティ関数
LP操作に必要な基本関数を提供
"""

import time
from web3 import Web3

# 定数
MAX_UINT128 = 2 ** 128 - 1
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
MAX_UINT256 = 2 ** 256 - 1

# Position Manager ABI（必要な関数のみ）
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
    },
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                    {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                    {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "internalType": "struct INonfungiblePositionManager.DecreaseLiquidityParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "decreaseLiquidity",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                    {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}
                ],
                "internalType": "struct INonfungiblePositionManager.CollectParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "collect",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]


def get_liquidity(w3, token_id):
    """NFTの流動性を取得"""
    try:
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)
        position_data = pm.functions.positions(token_id).call()
        return position_data[7]  # liquidity
    except Exception as e:
        print(f"❌ get_liquidity エラー: {e}")
        return 0


def decrease_liquidity(w3, wallet, token_id, liquidity_to_remove, amount0_min, amount1_min, gas=400000,
                       gas_price=2000000000):
    """流動性を減少させる"""
    try:
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        deadline = int(time.time()) + 3600  # 1時間後

        # DecreaseLiquidity params
        decrease_params = (
            token_id,
            liquidity_to_remove,
            amount0_min,
            amount1_min,
            deadline
        )

        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.decreaseLiquidity(decrease_params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": gas_price,
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        return tx_hash

    except Exception as e:
        print(f"❌ decrease_liquidity エラー: {e}")
        raise e


def collect_fees(w3, wallet, token_id, gas=300000, gas_price=2000000000):
    """手数料と残高を回収"""
    try:
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        # collect用のuint128最大値
        MAX_UINT128 = 2 ** 128 - 1

        # Collect params
        collect_params = (
            token_id,
            wallet.address,  # recipient
            MAX_UINT128,  # amount0Max（修正: uint128範囲内）
            MAX_UINT128   # amount1Max（修正: uint128範囲内）
        )

        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.collect(collect_params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": gas_price,
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        return tx_hash

    except Exception as e:
        print(f"❌ collect_fees エラー: {e}")
        raise e


def get_position_info(w3, token_id):
    """NFTポジションの詳細情報を取得"""
    try:
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)
        position_data = pm.functions.positions(token_id).call()

        return {
            "nonce": position_data[0],
            "operator": position_data[1],
            "token0": position_data[2],
            "token1": position_data[3],
            "fee": position_data[4],
            "tick_lower": position_data[5],
            "tick_upper": position_data[6],
            "liquidity": position_data[7],
            "fee_growth_inside0": position_data[8],
            "fee_growth_inside1": position_data[9],
            "tokens_owed0": position_data[10],
            "tokens_owed1": position_data[11]
        }

    except Exception as e:
        print(f"❌ get_position_info エラー: {e}")
        return None


def approve_if_needed(w3, wallet, token_address, spender, amount, gas=100000, gas_price=2000000000):
    """必要に応じてトークンをapprove"""
    try:
        # ERC20 ABI（approve用）
        erc20_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "spender", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "owner", "type": "address"},
                    {"internalType": "address", "name": "spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        token = w3.eth.contract(address=token_address, abi=erc20_abi)

        # 現在のallowanceを確認
        current_allowance = token.functions.allowance(wallet.address, spender).call()

        if current_allowance >= amount:
            print(f"✅ 既にapprove済み: {current_allowance}")
            return None

        # approve実行
        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = token.functions.approve(spender, MAX_UINT256).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": gas_price,
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"📝 approve送信: {w3.to_hex(tx_hash)}")
        return tx_hash

    except Exception as e:
        print(f"❌ approve_if_needed エラー: {e}")
        raise e


def add_liquidity(w3, wallet, token0, token1, fee, tick_lower, tick_upper, amount0_desired, amount1_desired,
                  amount0_min=0, amount1_min=0, gas=600000, gas_price=2000000000):
    """流動性を追加（新NFT作成）"""
    try:
        # Position Manager ABI（mint用）
        mint_abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {"internalType": "address", "name": "token0", "type": "address"},
                            {"internalType": "address", "name": "token1", "type": "address"},
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {"internalType": "int24", "name": "tickLower", "type": "int24"},
                            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                            {"internalType": "uint256", "name": "amount0Desired", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount1Desired", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount0Min", "type": "uint256"},
                            {"internalType": "uint256", "name": "amount1Min", "type": "uint256"},
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                        ],
                        "internalType": "struct INonfungiblePositionManager.MintParams",
                        "name": "params",
                        "type": "tuple"
                    }
                ],
                "name": "mint",
                "outputs": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                    {"internalType": "uint256", "name": "amount0", "type": "uint256"},
                    {"internalType": "uint256", "name": "amount1", "type": "uint256"}
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]

        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=mint_abi)

        deadline = int(time.time()) + 3600  # 1時間後

        # Mint params
        mint_params = (
            token0,
            token1,
            fee,
            tick_lower,
            tick_upper,
            amount0_desired,
            amount1_desired,
            amount0_min,
            amount1_min,
            wallet.address,  # recipient
            deadline
        )

        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        tx_data = pm.functions.mint(mint_params).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": gas_price,
            "value": 0
        })

        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        return tx_hash

    except Exception as e:
        print(f"❌ add_liquidity エラー: {e}")
        raise e


# 互換性のための関数エイリアス
def get_current_liquidity(w3, token_id):
    """get_liquidityの別名（互換性用）"""
    return get_liquidity(w3, token_id)


def remove_liquidity(w3, wallet, token_id, liquidity_percentage=1.0, gas=400000, gas_price=2000000000):
    """流動性を除去（パーセンテージ指定）"""
    try:
        # 現在の流動性を取得
        current_liquidity = get_liquidity(w3, token_id)

        if current_liquidity == 0:
            print("⚠️ 流動性が既に0です")
            return None

        # 除去する流動性を計算
        liquidity_to_remove = int(current_liquidity * liquidity_percentage)

        # decrease_liquidityを実行
        return decrease_liquidity(
            w3, wallet, token_id,
            liquidity_to_remove, 0, 0,  # amount0_min, amount1_min = 0
            gas, gas_price
        )

    except Exception as e:
        print(f"❌ remove_liquidity エラー: {e}")
        raise e


if __name__ == "__main__":
    """テスト実行"""
    print("=== 🔧 Uniswap Utils テスト ===")
    print("利用可能な関数:")
    print("- get_liquidity(w3, token_id)")
    print("- decrease_liquidity(w3, wallet, token_id, liquidity, amount0_min, amount1_min)")
    print("- collect_fees(w3, wallet, token_id)")
    print("- get_position_info(w3, token_id)")
    print("- approve_if_needed(w3, wallet, token_address, spender, amount)")
    print("- add_liquidity(w3, wallet, token0, token1, fee, tick_lower, tick_upper, amount0, amount1)")
    print("- remove_liquidity(w3, wallet, token_id, percentage)")