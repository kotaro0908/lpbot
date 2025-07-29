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


# ===== Multicall機能追加 =====
# Multicall V3 Address (Arbitrum One)
MULTICALL_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Multicall ABI（必要な関数のみ）
MULTICALL_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"}
                ],
                "internalType": "struct Multicall3.Call[]",
                "name": "calls",
                "type": "tuple[]"
            }
        ],
        "name": "aggregate",
        "outputs": [
            {"internalType": "uint256", "name": "blockNumber", "type": "uint256"},
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]


def encode_decrease_liquidity(token_id, liquidity_to_remove, amount0_min=0, amount1_min=0):
    """decreaseLiquidity関数呼び出しをエンコード（Web3標準機能使用）"""
    try:
        from web3 import Web3

        # deadline設定（1時間後）
        deadline = int(time.time()) + 3600

        # パラメータ構築
        decrease_params = (
            token_id,
            liquidity_to_remove,
            amount0_min,
            amount1_min,
            deadline
        )

        # Web3コントラクトを使ってエンコード
        w3 = Web3()
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        # 関数呼び出しデータを直接エンコード
        encoded_data = pm.encodeABI(fn_name="decreaseLiquidity", args=[decrease_params])

        return encoded_data

    except Exception as e:
        print(f"❌ encode_decrease_liquidity エラー: {e}")
        raise e


def encode_collect(token_id, recipient):
    """collect関数呼び出しをエンコード（Web3標準機能使用）"""
    try:
        from web3 import Web3

        # パラメータ構築（最大値で全回収）
        collect_params = (
            token_id,
            recipient,
            MAX_UINT128,  # amount0Max
            MAX_UINT128  # amount1Max
        )

        # Web3コントラクトを使ってエンコード
        w3 = Web3()
        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITION_MANAGER_ABI)

        # 関数呼び出しデータを直接エンコード
        encoded_data = pm.encodeABI(fn_name="collect", args=[collect_params])

        return encoded_data

    except Exception as e:
        print(f"❌ encode_collect エラー: {e}")
        raise e


def multicall_decrease_and_collect(w3, wallet, token_id, liquidity_to_remove, amount0_min, amount1_min, gas=800000,
                                   gas_price=2000000000):
    """Position Managerのmulticall機能を使用（Multicall3不使用）"""
    try:
        print(f"🔄 Position Manager Multicall開始: NFT {token_id}")

        # Position Manager ABI（multicall機能付き）
        MULTICALL_ABI = POSITION_MANAGER_ABI + [
            {
                "inputs": [{"internalType": "bytes[]", "name": "data", "type": "bytes[]"}],
                "name": "multicall",
                "outputs": [{"internalType": "bytes[]", "name": "results", "type": "bytes[]"}],
                "stateMutability": "payable",
                "type": "function"
            }
        ]

        pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=MULTICALL_ABI)

        # Step 1: decreaseLiquidityのcallDataを作成
        deadline = int(time.time()) + 3600
        decrease_params = (token_id, liquidity_to_remove, amount0_min, amount1_min, deadline)
        decrease_data = pm.encodeABI(fn_name="decreaseLiquidity", args=[decrease_params])

        # Step 2: collectのcallDataを作成
        collect_params = (token_id, wallet.address, MAX_UINT128, MAX_UINT128)
        collect_data = pm.encodeABI(fn_name="collect", args=[collect_params])

        print(f"📊 エンコード結果:")
        print(f"   decrease_data: {decrease_data[:100]}...")
        print(f"   collect_data: {collect_data[:100]}...")

        # Step 3: Position Managerのmulticallを実行
        nonce = w3.eth.get_transaction_count(wallet.address, 'pending')

        # multicall用のcallDataリスト
        multicall_data = [decrease_data, collect_data]

        # ガス見積もり
        try:
            gas_estimate = pm.functions.multicall(multicall_data).estimate_gas({
                "from": wallet.address,
                "value": 0
            })
            gas_limit = int(gas_estimate * 1.5)
            print(f"⛽ ガス見積もり成功: {gas_estimate:,} → {gas_limit:,}")
        except Exception as e:
            print(f"⚠️ ガス見積もり失敗: {e}")
            gas_limit = gas

        # トランザクション構築
        tx_data = pm.functions.multicall(multicall_data).build_transaction({
            "from": wallet.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "value": 0
        })

        # 署名・送信
        signed = wallet.sign_transaction(tx_data)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        print(f"📝 Position Manager Multicall送信: {tx_hash.hex()}")
        print(f"🔗 Arbiscan: https://arbiscan.io/tx/{tx_hash.hex()}")

        # 確認待機
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            print("✅ Position Manager Multicall成功!")
            return tx_hash
        else:
            print("❌ Position Manager Multicall失敗")
            return None

    except Exception as e:
        print(f"❌ multicall_decrease_and_collect エラー: {e}")
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
    print("- multicall_decrease_and_collect(w3, wallet, token_id, liquidity_to_remove)")