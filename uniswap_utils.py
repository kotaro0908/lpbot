from web3 import Web3
import time

POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"  # Uniswap V3 NFT Manager

# ...（decrease_liquidity, collect_fees, get_eth_usdc_price など既存部分はそのまま）...

MINT_ABI = [{
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
}]

def approve_if_needed(token_contract, wallet, spender, amount, w3):
    allowance = token_contract.functions.allowance(wallet.address, spender).call()
    if allowance < amount:
        tx = token_contract.functions.approve(spender, amount).build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": 80000,
            "gasPrice": w3.to_wei("2", "gwei")
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        print("approve tx sent:", w3.to_hex(tx_hash))
        w3.eth.wait_for_transaction_receipt(tx_hash)

def add_liquidity(
    w3, wallet, token0, token1, fee, tick_lower, tick_upper,
    amount0_desired, amount1_desired, amount0_min, amount1_min,
    recipient=None, gas=300000, gas_price=None
):
    pm = w3.eth.contract(address=POSITION_MANAGER_ADDRESS, abi=MINT_ABI)
    deadline = int(time.time()) + 600
    if recipient is None:
        recipient = wallet.address

    params = (
        token0, token1, fee, tick_lower, tick_upper,
        amount0_desired, amount1_desired,
        amount0_min, amount1_min,
        recipient, deadline
    )

    tx = pm.functions.mint(params).build_transaction({
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
        "gas": gas,
        "gasPrice": gas_price or w3.to_wei("2", "gwei"),
        "value": 0
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print("[INFO] addLiquidity(mint) tx sent:", w3.to_hex(tx_hash))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    # Mintイベント名は大文字に注意
    # events = pm.events.Mint().processReceipt(receipt)
    # if events: print("Minted tokenId:", events[0]['args']['tokenId'])
    return receipt
