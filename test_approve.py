# test_approve.py

import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()
RPC_URL     = os.getenv('RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')

# ← ここを直書きで変更
TOKEN_ID    = 4707661  # 新しいLP NFTのtokenIdをここに記載

NFT_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"  # Uniswap V3 PositionManager

NFT_ABI = [{
    "inputs": [
        {"internalType": "address", "name": "to", "type": "address"},
        {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
    ],
    "name": "approve",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

w3     = Web3(Web3.HTTPProvider(RPC_URL))
wallet = w3.eth.account.from_key(PRIVATE_KEY)
contract = w3.eth.contract(address=NFT_ADDRESS, abi=NFT_ABI)

# --- approveトランザクションを送信 ---
tx = contract.functions.approve(NFT_ADDRESS, TOKEN_ID).build_transaction({
    "from": wallet.address,
    "nonce": w3.eth.get_transaction_count(wallet.address),
    "gas": 100000,
    "gasPrice": w3.to_wei("2", "gwei")
})

signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet.key)
tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
print("approve tx sent:", w3.to_hex(tx_hash))
