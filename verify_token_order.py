from web3 import Web3
from env_config import RPC_URL

def verify_pool_tokens():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    pool_address = w3.to_checksum_address("0xc6962004f452bE9203591991D15f6b388e09e8d0")
    abi = [
        {"inputs": [], "name": "token0", "outputs":[{"internalType":"address","name":"","type":"address"}], "stateMutability":"view","type":"function"},
        {"inputs": [], "name": "token1", "outputs":[{"internalType":"address","name":"","type":"address"}], "stateMutability":"view","type":"function"},
    ]
    c = w3.eth.contract(address=pool_address, abi=abi)
    print("🧩 token0:", c.functions.token0().call())
    print("🧩 token1:", c.functions.token1().call())

if __name__ == "__main__":
    verify_pool_tokens()
