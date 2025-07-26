from web3 import Web3
from abi import ERC20_ABI, SWAP_ROUTER_ABI  # 必要に応じてABIを外部ファイル/定数に
from env_config import RPC_URL, PRIVATE_KEY, SWAP_PAIRS, SWAP_ROUTER_ADDRESS

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.eth.account.from_key(PRIVATE_KEY)

def get_token_balance(token_address, owner_address):
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return token.functions.balanceOf(owner_address).call()

def approve_if_needed(token_address, spender, amount):
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    allowance = token.functions.allowance(wallet.address, spender).call()
    if allowance < amount:
        tx = token.functions.approve(spender, amount).build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "gas": 80000,
            "gasPrice": w3.to_wei("2", "gwei")
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"[INFO] approve sent: {w3.to_hex(tx_hash)}")

def swap_exact_input(from_token, to_token, amount_in):
    router = w3.eth.contract(address=SWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI)
    params = {
        'tokenIn': from_token,
        'tokenOut': to_token,
        'fee': 500,  # 0.05%プール（適宜可変化OK）
        'recipient': wallet.address,
        'deadline': w3.eth.get_block('latest')['timestamp'] + 600,
        'amountIn': amount_in,
        'amountOutMinimum': 0,  # スリッページ制御は後で
        'sqrtPriceLimitX96': 0
    }
    tx = router.functions.exactInputSingle(params).build_transaction({
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
        "gas": 300000,
        "gasPrice": w3.to_wei("2", "gwei")
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"[INFO] swap sent: {w3.to_hex(tx_hash)}")

