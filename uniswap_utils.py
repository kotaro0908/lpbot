from web3 import Web3
import time

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

DECREASE_LIQUIDITY_ABI = [{
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
    "stateMutability": "nonpayable",
    "type": "function"
}]

COLLECT_ABI = [{
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
    "stateMutability": "nonpayable",
    "type": "function"
}]

POSITIONS_ABI = [{
    "inputs": [
        {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
    ],
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
        # ...省略
    ],
    "stateMutability": "view",
    "type": "function"
}]

def get_liquidity(w3: Web3, token_id: int) -> int:
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=POSITIONS_ABI)
    pos = pm.functions.positions(token_id).call()
    liquidity = pos[7]  # index 7がliquidity
    return liquidity

def decrease_liquidity(w3: Web3, wallet, token_id: int, liquidity: int, amount0_min: int, amount1_min: int, gas: int, gas_price: int):
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=DECREASE_LIQUIDITY_ABI)
    deadline = int(time.time()) + 300
    params = (token_id, liquidity, amount0_min, amount1_min, deadline)
    tx = pm.functions.decreaseLiquidity(params).build_transaction({
        'from': wallet.address,
        'nonce': w3.eth.get_transaction_count(wallet.address),
        'gas': gas,
        'gasPrice': gas_price
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print("decreaseLiquidity tx sent:", w3.to_hex(tx_hash))
    return tx_hash

def collect_fees(w3: Web3, wallet, token_id: int, gas: int, gas_price: int):
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=COLLECT_ABI)
    amount_max = 2**128 - 1
    params = (token_id, wallet.address, amount_max, amount_max)
    tx = pm.functions.collect(params).build_transaction({
        'from': wallet.address,
        'nonce': w3.eth.get_transaction_count(wallet.address),
        'gas': gas,
        'gasPrice': gas_price
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print("collect tx sent:", w3.to_hex(tx_hash))
    return tx_hash

# === ここから追加 ===

SLOT0_ABI = [{
    "inputs": [],
    "name": "slot0",
    "outputs": [
        {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"internalType": "int24", "name": "tick", "type": "int24"},
        {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
        {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
        {"internalType": "bool", "name": "unlocked", "type": "bool"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

def get_eth_usdc_price(w3, pool_address):
    """
    Uniswap V3 poolのslot0から現在のETH/USDC価格を取得
    :param w3: Web3インスタンス
    :param pool_address: ETH/USDCプールアドレス（例: 0xC696...）
    :return: 1ETH = ? USDC（float）
    """
    pool = w3.eth.contract(address=pool_address, abi=SLOT0_ABI)
    slot0 = pool.functions.slot0().call()
    sqrt_price_x96 = slot0[0]
    # ETH/USDC（USDCが6桁, ETHが18桁の場合）
    price = (sqrt_price_x96 ** 2 * (10 ** 12)) / (2 ** 192)
    return price

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    load_dotenv()
    RPC_URL = os.getenv("RPC_URL")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # プールアドレス（ETH/USDC, 0.05% tier）
    pool_address = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")
    price = get_eth_usdc_price(w3, pool_address)
    print(f"ETH/USDC price: 1ETH = {price} USDC")