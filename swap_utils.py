from web3 import Web3
from env_config import RPC_URL, PRIVATE_KEY, SWAP_ROUTER_ADDRESS

# --- 必要なABI ---
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]

# --- 初期化 ---
w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.eth.account.from_key(PRIVATE_KEY)

# --- 残高取得 ---
def get_token_balance(token_address, owner_address):
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return token.functions.balanceOf(owner_address).call()

# --- 桁取得（USDC=6, WETH=18） ---
def get_token_decimals(token_address):
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    try:
        return token.functions.decimals().call()
    except Exception:
        # Fallback: USDC/USDT=6, WETH/ETH=18
        if "usdc" in token_address.lower() or "usdt" in token_address.lower():
            return 6
        return 18

# --- approve ---
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
        w3.eth.wait_for_transaction_receipt(tx_hash)
    else:
        print(f"[INFO] already approved: allowance={allowance}")

# --- swap（Uniswap V3 SwapRouter exactInputSingle）---
def swap_exact_input(from_token, to_token, amount_in, fee=500, slippage=0.01):
    router = w3.eth.contract(address=SWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI)
    deadline = w3.eth.get_block('latest')['timestamp'] + 600
    amount_out_minimum = 0  # ← 本番ではOracle参照でslippage反映も推奨
    params = (
        from_token,
        to_token,
        fee,
        wallet.address,
        deadline,
        amount_in,
        amount_out_minimum,
        0
    )
    tx = router.functions.exactInputSingle(params).build_transaction({
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
        "gas": 300000,
        "gasPrice": w3.to_wei("2", "gwei"),
        "value": 0
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"[INFO] swap sent: {w3.to_hex(tx_hash)}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
