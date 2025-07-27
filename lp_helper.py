#!/usr/bin/env python3
"""
LP作成支援ツール（SWAP機能統合版）
LP作成直前の資金準備・最適配分計算・自動SWAP
"""

import os
import logging
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# 設定
RPC_URL = os.getenv("RPC_URL")
WETH_ADDRESS = os.getenv("WETH_ADDRESS")
USDC_ADDRESS = os.getenv("USDC_ADDRESS")
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
SWAP_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

# 安全設定
MIN_ETH_BUFFER = 0.008  # ガス代用ETH残高（SWAP+LP作成分）
MIN_USDC_BUFFER = 5.0  # 調整用USDC残高
TARGET_INVESTMENT_RATIO = 0.95  # 95%投入で安全マージン確保

# ERC20 ABI
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Pool ABI
POOL_ABI = [
    {
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
    }
]

logger = logging.getLogger(__name__)


class LPHelperWithSwap:
    def __init__(self, w3, wallet_address):
        self.w3 = w3
        self.wallet_address = w3.to_checksum_address(wallet_address)

        # コントラクト初期化
        self.weth_contract = w3.eth.contract(address=w3.to_checksum_address(WETH_ADDRESS), abi=ERC20_ABI)
        self.usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
        self.pool_contract = w3.eth.contract(address=w3.to_checksum_address(POOL_ADDRESS), abi=POOL_ABI)

    def get_eth_price(self):
        """ETH/USDC価格取得"""
        try:
            slot0 = self.pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]

            # sqrtPriceX96からETH価格計算
            price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
            eth_price_usd = price_raw * (10 ** 12)  # USDC per WETH

            return eth_price_usd if eth_price_usd > 0 else 3800  # フォールバック価格
        except Exception as e:
            logger.warning(f"価格取得エラー、フォールバック価格使用: {e}")
            return 3800  # フォールバック価格

    def get_wallet_balances(self):
        """ウォレット残高取得"""
        try:
            # ETH残高
            eth_balance_wei = self.w3.eth.get_balance(self.wallet_address)
            eth_balance = float(self.w3.from_wei(eth_balance_wei, 'ether'))

            # WETH残高
            weth_balance_wei = self.weth_contract.functions.balanceOf(self.wallet_address).call()
            weth_balance = float(self.w3.from_wei(weth_balance_wei, 'ether'))

            # USDC残高
            usdc_balance_wei = self.usdc_contract.functions.balanceOf(self.wallet_address).call()
            usdc_balance = float(usdc_balance_wei / 10 ** 6)  # USDC is 6 decimals

            return {
                'eth': eth_balance,
                'weth': weth_balance,
                'usdc': usdc_balance,
                'total_eth': eth_balance + weth_balance
            }
        except Exception as e:
            logger.error(f"残高取得エラー: {e}")
            return None

    def get_available_funds_for_lp(self):
        """LP作成用利用可能資金計算（SWAP考慮）"""
        balances = self.get_wallet_balances()
        eth_price = self.get_eth_price()

        if not balances:
            return None

        # 利用可能資金計算（ガス・バッファ除く）
        available_eth = max(0, balances['total_eth'] - MIN_ETH_BUFFER)
        available_usdc = max(0, balances['usdc'] - MIN_USDC_BUFFER)

        # 総利用可能価値（USD換算）
        available_eth_usd = available_eth * eth_price
        total_available_usd = available_eth_usd + available_usdc

        return {
            'balances': balances,
            'eth_price': eth_price,
            'available_eth': available_eth,
            'available_usdc': available_usdc,
            'available_eth_usd': available_eth_usd,
            'total_available_usd': total_available_usd
        }

    def calculate_optimal_allocation_with_swap(self, target_investment_ratio=TARGET_INVESTMENT_RATIO):
        """SWAP込みの最適LP配分計算"""
        funds = self.get_available_funds_for_lp()

        if not funds:
            return None

        # 95%投入額計算
        target_investment_usd = funds['total_available_usd'] * target_investment_ratio
        target_per_token_usd = target_investment_usd / 2  # 50:50配分

        # 必要なETH量計算
        required_eth_amount = target_per_token_usd / funds['eth_price']
        required_usdc_amount = target_per_token_usd

        # 現在のETH/USDC残高
        current_eth_usd = funds['available_eth'] * funds['eth_price']
        current_usdc_usd = funds['available_usdc']

        # SWAP必要量計算
        swap_info = self.calculate_swap_requirements(
            target_per_token_usd,
            current_eth_usd,
            current_usdc_usd,
            funds['eth_price']
        )

        return {
            'target_investment_usd': target_investment_usd,
            'target_per_token_usd': target_per_token_usd,
            'required_eth_amount': required_eth_amount,
            'required_usdc_amount': required_usdc_amount,
            'current_eth_usd': current_eth_usd,
            'current_usdc_usd': current_usdc_usd,
            'swap_info': swap_info,
            'eth_price': funds['eth_price']
        }

    def calculate_swap_requirements(self, target_per_token_usd, current_eth_usd, current_usdc_usd, eth_price):
        """必要なSWAP量計算"""
        swap_info = {
            'needs_swap': False,
            'swap_direction': None,
            'swap_amount_usd': 0,
            'swap_amount_token': 0,
            'final_eth_usd': 0,
            'final_usdc_usd': 0
        }

        # 不足量計算
        eth_shortage_usd = max(0, target_per_token_usd - current_eth_usd)
        usdc_shortage_usd = max(0, target_per_token_usd - current_usdc_usd)

        if eth_shortage_usd > 0 and current_usdc_usd >= target_per_token_usd + eth_shortage_usd:
            # USDC → ETH SWAP が必要
            swap_info.update({
                'needs_swap': True,
                'swap_direction': 'USDC_TO_ETH',
                'swap_amount_usd': eth_shortage_usd,
                'swap_amount_token': eth_shortage_usd,  # USDC amount
                'final_eth_usd': target_per_token_usd,
                'final_usdc_usd': target_per_token_usd
            })
        elif usdc_shortage_usd > 0 and current_eth_usd >= target_per_token_usd + usdc_shortage_usd:
            # ETH → USDC SWAP が必要
            swap_info.update({
                'needs_swap': True,
                'swap_direction': 'ETH_TO_USDC',
                'swap_amount_usd': usdc_shortage_usd,
                'swap_amount_token': usdc_shortage_usd / eth_price,  # ETH amount
                'final_eth_usd': target_per_token_usd,
                'final_usdc_usd': target_per_token_usd
            })
        else:
            # SWAPなしで可能な最大投入
            max_possible_per_token = min(current_eth_usd, current_usdc_usd)
            swap_info.update({
                'final_eth_usd': max_possible_per_token,
                'final_usdc_usd': max_possible_per_token
            })

        return swap_info

    def get_swap_execution_plan(self):
        """SWAP実行プラン取得"""
        allocation = self.calculate_optimal_allocation_with_swap()

        if not allocation or not allocation['swap_info']['needs_swap']:
            return None

        swap_info = allocation['swap_info']

        if swap_info['swap_direction'] == 'USDC_TO_ETH':
            return {
                'direction': 'USDC → ETH',
                'input_token': 'USDC',
                'output_token': 'ETH',
                'input_amount': swap_info['swap_amount_token'],
                'estimated_output': swap_info['swap_amount_token'] / allocation['eth_price'],
                'reason': f"ETH不足分 ${swap_info['swap_amount_usd']:.2f} を補充"
            }
        elif swap_info['swap_direction'] == 'ETH_TO_USDC':
            return {
                'direction': 'ETH → USDC',
                'input_token': 'ETH',
                'output_token': 'USDC',
                'input_amount': swap_info['swap_amount_token'],
                'estimated_output': swap_info['swap_amount_usd'],
                'reason': f"USDC不足分 ${swap_info['swap_amount_usd']:.2f} を補充"
            }

        return None

    def display_lp_preparation_with_swap(self):
        """SWAP込みLP作成準備状況表示"""
        funds = self.get_available_funds_for_lp()

        if not funds:
            print("❌ 資金情報取得失敗")
            return None

        print("\n" + "=" * 60)
        print("💰 LP作成資金準備（SWAP機能統合版）")
        print("=" * 60)

        # 現在残高
        print(f"📊 現在残高:")
        print(f"   ETH: {funds['balances']['eth']:.6f}")
        print(f"   WETH: {funds['balances']['weth']:.6f}")
        print(f"   USDC: {funds['balances']['usdc']:.2f}")
        print(f"   ETH価格: ${funds['eth_price']:.2f}")

        # 利用可能資金
        print(f"\n💎 利用可能資金（バッファ除く）:")
        print(f"   ETH+WETH: {funds['available_eth']:.6f} (${funds['available_eth_usd']:.2f})")
        print(f"   USDC: {funds['available_usdc']:.2f}")
        print(f"   合計: ${funds['total_available_usd']:.2f}")

        # 最適配分計算
        allocation = self.calculate_optimal_allocation_with_swap()

        if allocation:
            print(f"\n🎯 95%投入プラン:")
            print(f"   目標投入額: ${allocation['target_investment_usd']:.2f}")
            print(f"   ETH側: ${allocation['target_per_token_usd']:.2f}")
            print(f"   USDC側: ${allocation['target_per_token_usd']:.2f}")

            swap_info = allocation['swap_info']

            if swap_info['needs_swap']:
                print(f"\n🔄 必要なSWAP:")
                swap_plan = self.get_swap_execution_plan()
                if swap_plan:
                    print(f"   方向: {swap_plan['direction']}")
                    print(f"   金額: {swap_plan['input_amount']:.6f} {swap_plan['input_token']}")
                    print(f"   理由: {swap_plan['reason']}")

                print(f"\n📊 SWAP後の最終配分:")
                print(f"   ETH: ${swap_info['final_eth_usd']:.2f}")
                print(f"   USDC: ${swap_info['final_usdc_usd']:.2f}")
                print(f"   合計: ${swap_info['final_eth_usd'] + swap_info['final_usdc_usd']:.2f}")
            else:
                print(f"\n✅ SWAPなしで投入可能:")
                print(f"   ETH: ${swap_info['final_eth_usd']:.2f}")
                print(f"   USDC: ${swap_info['final_usdc_usd']:.2f}")
                print(f"   合計: ${swap_info['final_eth_usd'] + swap_info['final_usdc_usd']:.2f}")

        print(f"\n✅ LP作成準備完了（95%投入、5%安全マージン）")

        return funds

    def get_lp_creation_params(self):
        """LP作成用パラメータ取得（main.py連携用）"""
        allocation = self.calculate_optimal_allocation_with_swap()

        if not allocation:
            return None

        swap_info = allocation['swap_info']

        return {
            'needs_swap': swap_info['needs_swap'],
            'swap_plan': self.get_swap_execution_plan(),
            'final_eth_amount': swap_info['final_eth_usd'] / allocation['eth_price'],
            'final_usdc_amount': swap_info['final_usdc_usd'],
            'total_investment_usd': swap_info['final_eth_usd'] + swap_info['final_usdc_usd']
        }

    def check_swap_feasibility(self):
        """SWAP実行可能性チェック"""
        allocation = self.calculate_optimal_allocation_with_swap()

        if not allocation:
            return False, "資金情報取得失敗"

        swap_info = allocation['swap_info']

        if not swap_info['needs_swap']:
            return True, "SWAPなしで投入可能"

        # SWAP実行可能性チェック
        if swap_info['swap_direction'] == 'USDC_TO_ETH':
            if allocation['current_usdc_usd'] >= swap_info['swap_amount_usd']:
                return True, f"USDC→ETH SWAP可能（${swap_info['swap_amount_usd']:.2f}）"
            else:
                return False, f"USDC不足（必要: ${swap_info['swap_amount_usd']:.2f}, 利用可能: ${allocation['current_usdc_usd']:.2f}）"

        elif swap_info['swap_direction'] == 'ETH_TO_USDC':
            if allocation['current_eth_usd'] >= swap_info['swap_amount_usd']:
                return True, f"ETH→USDC SWAP可能（${swap_info['swap_amount_usd']:.2f}）"
            else:
                return False, f"ETH不足（必要: ${swap_info['swap_amount_usd']:.2f}, 利用可能: ${allocation['current_eth_usd']:.2f}）"

        return False, "不明なSWAP方向"


# テスト用メイン関数
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    wallet_address = os.getenv("WALLET_ADDRESS")

    # LP作成支援ツール初期化
    lp_helper = LPHelperWithSwap(w3, wallet_address)

    # LP作成準備状況表示
    lp_helper.display_lp_preparation_with_swap()

    # SWAP実行可能性チェック
    feasible, reason = lp_helper.check_swap_feasibility()
    print(f"\n🔍 SWAP実行可能性: {'✅' if feasible else '❌'} {reason}")

    # LP作成パラメータ取得
    params = lp_helper.get_lp_creation_params()
    if params:
        print(f"\n🚀 LP作成パラメータ:")
        print(f"   SWAP必要: {'Yes' if params['needs_swap'] else 'No'}")
        print(f"   最終ETH: {params['final_eth_amount']:.6f}")
        print(f"   最終USDC: {params['final_usdc_amount']:.2f}")
        print(f"   総投入額: ${params['total_investment_usd']:.2f}")