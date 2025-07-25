from uniswap_utils import add_liquidity, remove_liquidity, collect_fees, get_lp_position
from logger import log_info, log_error

class LPManager:
    def __init__(self, web3, wallet, pool, config):
        self.web3 = web3
        self.wallet = wallet
        self.pool = pool
        self.config = config

    def withdraw_and_redeploy(self, token_id):
        try:
            # 1. 現在のLPポジションを撤退
            remove_liquidity(self.web3, self.wallet, token_id)
            log_info(f"Liquidity removed for NFT {token_id}")

            # 2. 報酬回収
            collect_fees(self.web3, self.wallet, token_id)
            log_info(f"Fees collected for NFT {token_id}")

            # 3. 必要通貨にスワップ（省略：後述）
            # swap_tokens_if_needed()

            # 4. 設定レンジで再度LP提供
            tick_lower, tick_upper = self.config['tick_lower'], self.config['tick_upper']
            add_liquidity(self.web3, self.wallet, self.pool, tick_lower, tick_upper)
            log_info(f"Liquidity re-added for {tick_lower} ~ {tick_upper}")

        except Exception as e:
            log_error(f"LP操作エラー: {str(e)}")

    def get_current_position(self):
        return get_lp_position(self.web3, self.wallet, self.pool)

# --- 使い方例（main.pyやAPSchedulerから呼び出し）
# manager = LPManager(web3, wallet, pool, config)
# current_nft = manager.get_current_position()
# manager.withdraw_and_redeploy(current_nft['token_id'])
