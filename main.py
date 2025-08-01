#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
import logging
from web3 import Web3
from dotenv import load_dotenv
from json_logger import JSONLogger  # ← この行を追加

# 両方の.envファイルを読み込む
load_dotenv('.env')  # 公開可能な設定
load_dotenv('.env.secret')  # 秘密鍵

# 設定
RPC_URL = os.getenv("RPC_URL")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
USDC_ADDRESS = os.getenv("USDC_ADDRESS")
WETH_ADDRESS = os.getenv("WETH_ADDRESS")

# Uniswap V3 設定
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"  # USDC/WETH 0.05%
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# 監視設定
MONITORING_INTERVAL = 30  # 秒
REBALANCE_THRESHOLD = 0.05  # 5%の閾値

# LP Helper設定
MIN_ETH_BUFFER = float(os.getenv("MIN_ETH_BUFFER", "0.008"))
MIN_USDC_BUFFER = float(os.getenv("MIN_USDC_BUFFER", "5.0"))
TARGET_INVESTMENT_RATIO = 0.95  # 95%投入で安全マージン確保

# Position Manager ABI
POSITION_MANAGER_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
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
    }
]

# Pool ABI（現在価格取得用）
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

# ERC20 ABI（LP Helper用）
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WalletNFTDetector:
    def __init__(self, w3, wallet_address, position_manager):
        self.w3 = w3
        self.wallet_address = wallet_address.lower()
        self.position_manager = position_manager

    def search_nfts_by_transfer_events(self):
        """Transfer イベントから効率的にNFT検索"""
        logger.info("🔍 Transfer イベントからウォレット所有NFT検索開始...")

        try:
            current_block = self.w3.eth.block_number
            logger.info(f"📊 現在ブロック: {current_block}")

            # Transfer イベントシグネチャ
            transfer_signature = self.w3.keccak(text="Transfer(address,address,uint256)")

            # ウォレットアドレスを正しくpadding（32バイト = 64文字にゼロパディング）
            wallet_padded = '0x' + '0' * 24 + self.wallet_address[2:].lower()

            found_nfts = set()

            # 段階的検索（10,000ブロック制限対応）
            search_ranges = [
                (2000, "最新2,000ブロック"),
                (5000, "最新5,000ブロック"),
                (8000, "最新8,000ブロック"),
                (10000, "最新10,000ブロック")
            ]

            for block_range, description in search_ranges:
                from_block = current_block - block_range
                to_block = current_block

                logger.info(f"🔍 {description} 検索中...")
                logger.info(f"   ブロック範囲: {from_block} ～ {to_block}")

                try:
                    # Transfer イベントフィルター（受信者としてウォレットを指定）
                    filter_params = {
                        'address': POSITION_MANAGER_ADDRESS,
                        'topics': [
                            transfer_signature.hex(),
                            None,  # from (any address)
                            wallet_padded  # to (padded wallet address)
                        ],
                        'fromBlock': from_block,
                        'toBlock': to_block
                    }

                    logs = self.w3.eth.get_logs(filter_params)
                    logger.info(f"   📊 {len(logs)}個のTransferイベント発見")

                    # NFT IDを抽出
                    for log in logs:
                        if len(log.topics) >= 4:
                            # topic[3]がNFT ID（uint256）
                            nft_id = int(log.topics[3].hex(), 16)
                            found_nfts.add(nft_id)

                    if len(logs) > 0:
                        logger.info(f"   ✅ この範囲で{len(found_nfts)}個のユニークNFT発見")
                    else:
                        logger.info(f"   📍 この範囲では対象NFTなし")

                except Exception as e:
                    if "413" in str(e) or "Request Entity Too Large" in str(e):
                        logger.warning(f"   ⚠️ 範囲が大きすぎます - RPC制限")
                        continue
                    else:
                        logger.error(f"   ❌ 検索エラー: {e}")
                        continue

            if not found_nfts:
                logger.warning("📍 Transfer イベント検索でNFTが見つかりませんでした")
                return []

            logger.info(f"📊 Transfer検索結果: {len(found_nfts)}個のNFT候補")
            logger.info(f"🎯 NFT ID一覧: {sorted(found_nfts)}")

            return sorted(found_nfts)

        except Exception as e:
            logger.error(f"❌ Transfer イベント検索エラー: {e}")
            return []

    def verify_ownership_and_liquidity(self, nft_ids):
        """NFTの所有確認と流動性チェック"""
        logger.info(f"🔍 {len(nft_ids)}個のNFTの所有・流動性確認中...")

        active_nfts = []

        for nft_id in nft_ids:
            try:
                # 所有者確認
                owner = self.position_manager.functions.ownerOf(nft_id).call()

                if owner.lower() != self.wallet_address:
                    logger.info(f"   📍 NFT {nft_id}: 他の人のNFT（スキップ）")
                    continue

                # ポジション詳細取得
                position = self.position_manager.functions.positions(nft_id).call()
                liquidity = position[7]  # liquidity
                tick_lower = position[5]  # tickLower
                tick_upper = position[6]  # tickUpper
                tokens_owed_0 = position[10]  # tokensOwed0
                tokens_owed_1 = position[11]  # tokensOwed1

                if liquidity > 0:
                    logger.info(f"   ✅ NFT {nft_id}: アクティブ（流動性 {liquidity}）")
                    active_nfts.append({
                        'token_id': nft_id,
                        'liquidity': liquidity,
                        'tick_lower': tick_lower,
                        'tick_upper': tick_upper
                    })
                else:
                    status = "非アクティブ（流動性なし）"
                    if tokens_owed_0 > 0 or tokens_owed_1 > 0:
                        status += f" - 手数料蓄積: {tokens_owed_0}, {tokens_owed_1}"
                    logger.info(f"   📍 NFT {nft_id}: {status}")

            except Exception as e:
                logger.warning(f"   ❌ NFT {nft_id} チェックエラー: {e}")
                continue

        return active_nfts

    def detect_wallet_nfts(self):
        """ウォレット所有NFT完全検索"""
        logger.info("🔍 初回起動: ウォレット所有NFT自動検出開始...")

        # 1. Transfer イベントでNFT候補を検索
        nft_candidates = self.search_nfts_by_transfer_events()

        if not nft_candidates:
            logger.warning("📍 NFT候補が見つかりませんでした")
            return []

        # 2. 所有確認と流動性チェック
        active_nfts = self.verify_ownership_and_liquidity(nft_candidates)

        if active_nfts:
            logger.info(f"🎯 アクティブNFT発見: {len(active_nfts)}個")
            for nft in active_nfts:
                logger.info(
                    f"   NFT {nft['token_id']}: 流動性 {nft['liquidity']}, レンジ [{nft['tick_lower']}, {nft['tick_upper']}]")
        else:
            logger.warning("📍 アクティブなNFTは見つかりませんでした")

        return active_nfts


class LPHelperIntegrated:
    """LP作成支援機能（main.py統合版）"""

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
            return 3800

    def get_available_funds_for_lp(self):
        """LP作成用利用可能資金計算"""
        try:
            # ETH残高
            eth_balance_wei = self.w3.eth.get_balance(self.wallet_address)
            eth_balance = float(self.w3.from_wei(eth_balance_wei, 'ether'))

            # WETH残高
            weth_balance_wei = self.weth_contract.functions.balanceOf(self.wallet_address).call()
            weth_balance = float(self.w3.from_wei(weth_balance_wei, 'ether'))

            # USDC残高
            usdc_balance_wei = self.usdc_contract.functions.balanceOf(self.wallet_address).call()
            usdc_balance = float(usdc_balance_wei / 10 ** 6)

            # 利用可能資金計算
            available_eth = max(0, eth_balance + weth_balance - MIN_ETH_BUFFER)
            available_usdc = max(0, usdc_balance - MIN_USDC_BUFFER)

            eth_price = self.get_eth_price()
            available_eth_usd = available_eth * eth_price
            total_available_usd = available_eth_usd + available_usdc

            return {
                'available_eth': available_eth,
                'available_usdc': available_usdc,
                'available_eth_usd': available_eth_usd,
                'total_available_usd': total_available_usd,
                'eth_price': eth_price,
                'current_eth_balance': eth_balance,
                'current_weth_balance': weth_balance,
                'current_usdc_balance': usdc_balance
            }
        except Exception as e:
            logger.error(f"資金状況取得エラー: {e}")
            return None

    def calculate_optimal_lp_amounts(self):
        """最適LP投入額計算（95%投入、SWAP考慮、WETH不足時調整対応）"""
        funds = self.get_available_funds_for_lp()
        if not funds:
            return None

        # 95%投入額計算
        target_investment_usd = funds['total_available_usd'] * TARGET_INVESTMENT_RATIO
        target_per_token_usd = target_investment_usd / 2

        # 現在の資金状況
        current_eth_usd = funds['available_eth_usd']
        current_usdc_usd = funds['available_usdc']

        # 🔧 修正: WETH確保可能性をチェック
        # 利用可能ETH（ETH + WETH - ガスバッファ）
        usable_eth_for_weth = max(0, funds['current_eth_balance'] - 0.005)  # 0.005 ETHはガスバッファ
        max_possible_weth = funds['current_weth_balance'] + usable_eth_for_weth
        max_possible_weth_usd = max_possible_weth * funds['eth_price']

        # WETH制約による投入額調整
        weth_constrained_amount = min(target_per_token_usd, max_possible_weth_usd)

        # SWAP必要性判定
        needs_swap = False
        swap_direction = None
        swap_amount = 0

        if current_eth_usd < weth_constrained_amount and current_usdc_usd >= weth_constrained_amount:
            # USDC → ETH SWAP必要
            needs_swap = True
            swap_direction = "USDC_TO_ETH"
            swap_amount = weth_constrained_amount - current_eth_usd
        elif current_usdc_usd < weth_constrained_amount and current_eth_usd >= weth_constrained_amount:
            # ETH → USDC SWAP必要
            needs_swap = True
            swap_direction = "ETH_TO_USDC"
            swap_amount = weth_constrained_amount - current_usdc_usd

        # 最終投入額計算（WETH制約考慮）
        if needs_swap:
            final_eth_usd = weth_constrained_amount
            final_usdc_usd = weth_constrained_amount
        else:
            # SWAPなしで可能な最大投入（WETH制約考慮）
            max_possible = min(current_eth_usd, current_usdc_usd, weth_constrained_amount)
            final_eth_usd = max_possible
            final_usdc_usd = max_possible

        # 🔧 修正: WETH制約により調整された場合の警告
        if weth_constrained_amount < target_per_token_usd:
            logger.warning(f"⚠️ WETH制約により投入額調整: ${target_per_token_usd:.2f} → ${weth_constrained_amount:.2f}")

        return {
            'needs_swap': needs_swap,
            'swap_direction': swap_direction,
            'swap_amount': swap_amount,
            'final_eth_amount': final_eth_usd / funds['eth_price'],
            'final_usdc_amount': final_usdc_usd,
            'total_investment_usd': final_eth_usd + final_usdc_usd,
            'eth_price': funds['eth_price'],
            'weth_constrained': weth_constrained_amount < target_per_token_usd
        }


class LPManager:
    def __init__(self, w3, pool_address, position_manager_address):
        self.w3 = w3
        self.pool = w3.eth.contract(address=pool_address, abi=POOL_ABI)
        self.position_manager = w3.eth.contract(address=position_manager_address, abi=POSITION_MANAGER_ABI)
        self.tracked_nfts = []

        # NFT検出システム
        self.nft_detector = WalletNFTDetector(w3, WALLET_ADDRESS, self.position_manager)

        # LP作成支援システム（新機能）
        self.lp_helper = LPHelperIntegrated(w3, WALLET_ADDRESS)

        # 🆕 前回残高を記録（増資検知用）
        self.previous_balances = {
            'eth': 0,
            'weth': 0,
            'usdc': 0,
            'total_usd': 0
        }
        self.MIN_DEPOSIT_THRESHOLD = 10.0  # $10以上の入金で反応

        # ERC20コントラクト初期化（残高確認用）
        self.weth_contract = w3.eth.contract(address=w3.to_checksum_address(WETH_ADDRESS), abi=ERC20_ABI)
        self.usdc_contract = w3.eth.contract(address=w3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)

    def check_balance_changes(self):
        """残高変化を検知（簡易版 - ウォレット残高のみ）"""
        try:
            # 現在の残高取得
            eth_balance = self.w3.eth.get_balance(WALLET_ADDRESS)
            weth_balance = self.weth_contract.functions.balanceOf(WALLET_ADDRESS).call()
            usdc_balance = self.usdc_contract.functions.balanceOf(WALLET_ADDRESS).call()

            # 単位変換
            current_eth = eth_balance / 10 ** 18
            current_weth = weth_balance / 10 ** 18
            current_usdc = usdc_balance / 10 ** 6

            # ETH価格取得
            eth_price = self.lp_helper.get_eth_price()

            # ウォレット内総資産
            wallet_total_usd = ((current_eth + current_weth) * eth_price) + current_usdc

            # 利用可能資金（バッファ除く）
            available_funds = wallet_total_usd - (MIN_ETH_BUFFER * eth_price + MIN_USDC_BUFFER)

            logger.info(f"💰 ウォレット残高: ${wallet_total_usd:.2f}")
            logger.info(f"   利用可能資金: ${available_funds:.2f}")

            # 初回チェック
            if self.previous_balances['total_usd'] == 0:
                self.previous_balances = {
                    'eth': current_eth,
                    'weth': current_weth,
                    'usdc': current_usdc,
                    'total_usd': wallet_total_usd
                }

                # 利用可能資金が$20以上あればリバランス
                if available_funds > 20:
                    logger.info(f"💡 初回起動時に利用可能資金検出: ${available_funds:.2f}")

                    # 🆕 追跡中のNFTがあるかチェック
                    if self.tracked_nfts:
                        logger.info(f"📍 追跡NFTあり: {self.tracked_nfts}")
                        # NFTがあっても資金があるなら、NFTは既に古い可能性
                        # （前回のLP作成が少額だった等）

                    return True

                return False

            # 前回からの増加チェック
            usd_increase = wallet_total_usd - self.previous_balances['total_usd']

            # リバランス判定
            if usd_increase >= self.MIN_DEPOSIT_THRESHOLD:
                # 新規入金
                logger.info(f"💵 新規入金検出: +${usd_increase:.2f}")

                # JSONログ追加
                JSONLogger.log_fund_change(
                    change_type="deposit",
                    amount_usd=usd_increase,
                    trigger_action="rebalance"
                )

                trigger = True
            elif available_funds > 20:
                # 利用可能資金が多い
                logger.info(f"💵 利用可能資金検出: ${available_funds:.2f}")
                trigger = True
            else:
                trigger = False

            if trigger:
                # 残高を更新
                self.previous_balances = {
                    'eth': current_eth,
                    'weth': current_weth,
                    'usdc': current_usdc,
                    'total_usd': wallet_total_usd
                }

                # 🆕 追跡中のNFTがあるかチェック
                if self.tracked_nfts:
                    logger.info(f"📍 追跡NFTあり: {self.tracked_nfts}")
                    # NFTがあれば、それをリバランスする
                    # （check_and_rebalance_if_neededでリバランスが実行される）

                return True

            return False

        except Exception as e:
            logger.error(f"❌ 残高チェックエラー: {e}")
            return False

    def load_tracked_nfts(self):
        """追跡NFTリストを読み込み"""
        try:
            with open('tracked_nfts.json', 'r') as f:
                data = json.load(f)
                self.tracked_nfts = data.get('nft_ids', [])
                logger.info(f"📁 追跡NFT読み込み: {self.tracked_nfts}")
        except FileNotFoundError:
            logger.info("📁 tracked_nfts.json が見つかりません - 初回起動として処理")
            self.tracked_nfts = []
        except Exception as e:
            logger.error(f"NFT履歴読み込みエラー: {e}")
            self.tracked_nfts = []

    def save_tracked_nfts(self):
        """追跡NFTリストを保存"""
        try:
            with open('tracked_nfts.json', 'w') as f:
                json.dump({'nft_ids': self.tracked_nfts}, f)
            logger.info(f"💾 追跡NFT保存完了: {self.tracked_nfts}")
        except Exception as e:
            logger.error(f"NFT履歴保存エラー: {e}")

    def detect_and_add_wallet_nfts(self):
        """ウォレットNFT自動検出・追加"""
        if self.tracked_nfts:
            logger.info(f"📁 既存追跡NFT: {self.tracked_nfts}")
            return True

        # ウォレット所有NFT検出
        active_nfts = self.nft_detector.detect_wallet_nfts()

        if active_nfts:
            # 検出されたNFTを追跡リストに追加
            detected_ids = [nft['token_id'] for nft in active_nfts]
            self.tracked_nfts = detected_ids
            self.save_tracked_nfts()

            logger.info(f"✅ ウォレットNFT自動検出完了: {len(detected_ids)}個のNFTを追跡開始")
            for nft in active_nfts:
                logger.info(f"   NFT {nft['token_id']}: レンジ [{nft['tick_lower']}, {nft['tick_upper']}]")

            return True
        else:
            logger.info("💡 アクティブなNFTが見つかりませんでした")
            return False

    def get_current_tick(self):
        """現在のtickを取得"""
        try:
            slot0 = self.pool.functions.slot0().call()
            return slot0[1]  # tick
        except Exception as e:
            logger.error(f"現在tick取得エラー: {e}")
            return None

    def get_position_info(self, token_id):
        """ポジション情報を取得"""
        try:
            position = self.position_manager.functions.positions(token_id).call()
            return {
                'liquidity': position[7],
                'tick_lower': position[5],
                'tick_upper': position[6],
                'tokens_owed_0': position[10],
                'tokens_owed_1': position[11]
            }
        except Exception as e:
            logger.error(f"NFT {token_id} ポジション情報取得エラー: {e}")
            return None

    def is_position_in_range(self, current_tick, tick_lower, tick_upper, threshold=REBALANCE_THRESHOLD):
        """ポジションがレンジ内かチェック"""
        tick_range = tick_upper - tick_lower
        buffer = int(tick_range * threshold)
        effective_lower = tick_lower + buffer
        effective_upper = tick_upper - buffer
        return effective_lower <= current_tick <= effective_upper

    def check_and_rebalance_if_needed(self):
        """レンジチェックと必要時リバランス実行（修正版）"""
        current_tick = self.get_current_tick()
        if current_tick is None:
            return

        logger.info(f"📊 現在tick: {current_tick}")

        # 🆕 資金追加チェック（最初に実行）
        fund_change_detected = self.check_balance_changes()
        if fund_change_detected:
            logger.info("🔄 資金追加によるリバランスチェック開始")

            # 🆕 LP価値をチェック
            has_active_lp = False
            for token_id in self.tracked_nfts:
                position_info = self.get_position_info(token_id)
                if position_info and position_info['liquidity'] > 0:
                    has_active_lp = True
                    break

            if self.tracked_nfts:
                # NFTが存在すれば無条件でリバランス
                logger.info(f"🔄 既存NFTのリバランス実行: {self.tracked_nfts[0]}")
                self.rebalance_position(self.tracked_nfts[0])
            else:
                logger.info("🆕 アクティブなLPなし - 新規LP作成実行")
                self.add_initial_liquidity()

            return  # ⚠️ ここで終了してしまう！

        # 🔴 以下のレンジチェックコードが実行されない！

        # 追跡NFTが空の場合は自動検出を試行
        if not self.tracked_nfts:
            logger.info("📍 追跡中のNFTがありません")
            if self.detect_and_add_wallet_nfts():
                logger.info("✅ ウォレットNFT自動検出で追跡開始")
            else:
                logger.info("🔵 アクティブなLPポジションなし - LP追加を実行")
                self.add_initial_liquidity()
                return

        # 追跡NFTの状況確認
        logger.info(f"🔍 追跡NFT確認: {self.tracked_nfts}")

        active_nfts = []
        out_of_range_nfts = []

        for token_id in self.tracked_nfts[:]:  # コピーを作成して安全に反復
            position_info = self.get_position_info(token_id)

            if position_info is None:
                logger.warning(f"⚠️ NFT {token_id}: アクセス不可（削除）")
                self.tracked_nfts.remove(token_id)
                continue

            if position_info['liquidity'] == 0:
                logger.info(f"📍 NFT {token_id}: 流動性なし（非アクティブ）")
                self.tracked_nfts.remove(token_id)
                continue

            logger.info(f"✅ NFT {token_id}: 流動性 {position_info['liquidity']}")
            active_nfts.append(token_id)

            # レンジチェック
            in_range = self.is_position_in_range(
                current_tick,
                position_info['tick_lower'],
                position_info['tick_upper']
            )

            # 🔧 デバッグ出力（バグ特定用）
            print(f"🔧 DEBUG: current_tick={current_tick}")
            print(f"🔧 DEBUG: tick_lower={position_info['tick_lower']}")
            print(f"🔧 DEBUG: tick_upper={position_info['tick_upper']}")
            print(f"🔧 DEBUG: in_range={in_range}")

            # 手動計算での確認
            tick_range = position_info['tick_upper'] - position_info['tick_lower']
            buffer = int(tick_range * REBALANCE_THRESHOLD)
            effective_lower = position_info['tick_lower'] + buffer
            effective_upper = position_info['tick_upper'] - buffer
            manual_check = effective_lower <= current_tick <= effective_upper
            print(f"🔧 DEBUG: effective_range=[{effective_lower}, {effective_upper}]")
            print(f"🔧 DEBUG: manual_calculation={manual_check}")

            logger.info(
                f"NFT {token_id}: 現在:{current_tick}, レンジ:[{position_info['tick_lower']}, {position_info['tick_upper']}]")

            if in_range:
                logger.info(f"✅ NFT {token_id} レンジ内")
            else:
                logger.info(f"🔴 NFT {token_id} レンジ外 - リバランス対象")
                out_of_range_nfts.append(token_id)

                # JSONログ追加
                JSONLogger.log_to_json("range_detection", {
                    "nft_id": token_id,
                    "current_tick": current_tick,
                    "tick_lower": position_info['tick_lower'],
                    "tick_upper": position_info['tick_upper'],
                    "in_range": False,
                    "price": self.lp_helper.get_eth_price() if hasattr(self, 'lp_helper') else None
                })

        # 追跡リスト更新
        if len(self.tracked_nfts) != len(active_nfts):
            self.tracked_nfts = active_nfts
            self.save_tracked_nfts()

        # 結果表示
        if active_nfts:
            logger.info(f"🎯 アクティブNFT: {active_nfts} ({len(active_nfts)}個)")
        else:
            logger.info("📍 アクティブなNFTがありません")
            self.add_initial_liquidity()
            return

        # リバランス実行
        if out_of_range_nfts:
            logger.info(f"🔄 {len(out_of_range_nfts)}個のNFTがリバランス対象")
            for token_id in out_of_range_nfts:
                self.rebalance_position(token_id)
        else:
            logger.info("🟢 全ポジションがレンジ内 - 監視継続")

    def add_initial_liquidity(self):
        """初回LP追加（最大資金活用版）"""
        logger.info("🚀 初回LP追加を自動実行中...")

        # 🆕 レンジ更新（ここに追加）
        logger.info("📊 最新レンジを計算...")
        result = subprocess.run(["python", "range_analyzer.py"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ レンジ更新完了")
        else:
            logger.warning("⚠️ レンジ更新失敗（既存のレンジを使用）")

        # JSONログ追加
        JSONLogger.log_system(
            log_level="INFO",
            function_name="add_initial_liquidity",
            message="Initial LP creation started"
        )

        try:
            # 💰 LP Helper: 最適投入額計算
            logger.info("💰 最大投入可能額を計算中...")

            optimal_amounts = self.lp_helper.calculate_optimal_lp_amounts()

            if optimal_amounts and optimal_amounts['total_investment_usd'] < 1.0:
                logger.warning(f"⚠️ 投入可能額が不足: ${optimal_amounts['total_investment_usd']:.2f} < $1.00")
                return

            if optimal_amounts:
                logger.info(f"📊 最適投入額: ${optimal_amounts['total_investment_usd']:.2f}")
                logger.info(f"   ETH: {optimal_amounts['final_eth_amount']:.6f}")
                logger.info(f"   USDC: {optimal_amounts['final_usdc_amount']:.2f}")

                # 🔧 修正: WETH制約による調整の表示
                if optimal_amounts.get('weth_constrained', False):
                    logger.info("⚠️ WETH残高制約により投入額を調整しました")

                if optimal_amounts['needs_swap']:
                    logger.info(f"🔄 SWAP必要: {optimal_amounts['swap_direction']}")
                    logger.info(f"   SWAP額: ${optimal_amounts['swap_amount']:.2f}")
                else:
                    logger.info("✅ SWAPなしで投入可能")

                # 最適化投入
                result = subprocess.run([
                    "python", "add_liquidity.py",
                    "--eth", str(optimal_amounts['final_eth_amount']),
                    "--usdc", str(optimal_amounts['final_usdc_amount']),
                    "--auto"
                ], text=True, capture_output=True, timeout=60)
            else:
                logger.warning("⚠️ 最適投入額計算失敗 - 従来方式で実行")

                # フォールバック（従来方式）
                result = subprocess.run([
                    "python", "add_liquidity.py"
                ], input="2\n", text=True, capture_output=True, timeout=60)

            if result.returncode == 0:
                logger.info("✅ 初回LP追加成功")

                # 出力からトランザクションハッシュを抽出
                output_lines = result.stdout.split('\n')
                tx_hash = None
                for line in output_lines:
                    if 'transaction hash:' in line.lower() or 'tx hash:' in line.lower():
                        tx_hash = line.split(':')[-1].strip()
                        break
                    if line.startswith('0x') and len(line) == 66:
                        tx_hash = line.strip()
                        break

                if tx_hash:
                    logger.info(f"📝 トランザクションハッシュ: {tx_hash}")

                    # トランザクション解析でNFT IDを取得
                    new_nft_id = self.extract_nft_id_from_transaction(tx_hash)
                    if new_nft_id:
                        logger.info(f"✅ NFT Mint検出: Token ID {new_nft_id}")
                        logger.info(f"🎯 新しいNFT追跡開始: {new_nft_id}")

                        self.tracked_nfts.append(new_nft_id)
                        self.save_tracked_nfts()

                        logger.info(f"✅ LP追加成功: NFT {new_nft_id} を追跡開始")

                        # JSONログ追加 - 成功
                        JSONLogger.log_to_json("lp_initialization", {
                            "nft_id": new_nft_id,
                            "tx_hash": tx_hash,
                            "investment_usd": optimal_amounts['total_investment_usd'] if optimal_amounts else None,
                            "success": True
                        })
                    else:
                        logger.warning("⚠️ NFT ID取得失敗 - 次回スキャンで検出予定")
                else:
                    logger.warning("⚠️ トランザクションハッシュ取得失敗")

            else:
                logger.error(f"❌ LP追加失敗: {result.stderr}")

                # JSONログ追加 - 失敗
                JSONLogger.log_system(
                    log_level="ERROR",
                    function_name="add_initial_liquidity",
                    message="Initial LP creation failed",
                    error_details=result.stderr[:500] if result.stderr else "No error output"
                )

        except subprocess.TimeoutExpired:
            logger.error("❌ LP追加タイムアウト")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="add_initial_liquidity",
                message="LP addition timeout",
                error_details="Execution exceeded 60 seconds"
            )
        except Exception as e:
            logger.error(f"❌ LP追加エラー: {e}")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="add_initial_liquidity",
                message="LP addition error",
                error_details=str(e)
            )

        # main.pyのadd_initial_liquidity関数内で
        print(f"🔧 DEBUG: optimal_amounts = {optimal_amounts}")
        print(
            f"🔧 DEBUG: subprocess args = {['python', 'add_liquidity.py', '--eth', str(optimal_amounts['final_eth_amount']), '--usdc', str(optimal_amounts['final_usdc_amount']), '--auto']}")

        # subprocess.run実行後
        print(f"🔧 DEBUG: returncode = {result.returncode}")
        print(f"🔧 DEBUG: stdout = {result.stdout}")
        print(f"🔧 DEBUG: stderr = {result.stderr}")

    def extract_nft_id_from_transaction(self, tx_hash):
        """トランザクションからNFT IDを抽出"""
        try:
            logger.info(f"🔍 トランザクション解析: {tx_hash}")

            # トランザクションレシート取得（最大30秒待機）
            receipt = None
            for attempt in range(30):
                try:
                    receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                    break
                except:
                    time.sleep(1)
                    continue

            if not receipt:
                logger.error("❌ トランザクションレシート取得失敗")
                return None

            # Transfer イベント検索
            transfer_signature = self.w3.keccak(text="Transfer(address,address,uint256)")

            for log in receipt.logs:
                if (log.address.lower() == POSITION_MANAGER_ADDRESS.lower() and
                        len(log.topics) >= 4 and
                        log.topics[0] == transfer_signature):

                    # topic[1] = from, topic[2] = to, topic[3] = tokenId
                    from_address = log.topics[1].hex()
                    to_address = log.topics[2].hex()

                    # Mint検出（from = 0x000...000）
                    if from_address == "0x0000000000000000000000000000000000000000000000000000000000000000":
                        token_id = int(log.topics[3].hex(), 16)
                        logger.info(f"✅ NFT Mint検出: Token ID {token_id}")
                        return token_id

            logger.warning("⚠️ NFT Mint イベントが見つかりませんでした")
            return None

        except Exception as e:
            logger.error(f"❌ トランザクション解析エラー: {e}")
            return None

    def rebalance_position(self, token_id):
        """個別ポジションのリバランス"""
        logger.info(f"🔄 NFT {token_id} のリバランス開始")

        # JSONログ追加 - リバランス開始
        JSONLogger.log_to_json("rebalance_trigger", {
            "nft_id": token_id,
            "reason": "range_out",  # または "fund_added" - 呼び出し元に応じて変更
            "current_price": self.lp_helper.get_eth_price() if hasattr(self, 'lp_helper') else None,
            "timestamp": time.time()
        })

        try:
            # リバランススクリプト実行
            result = subprocess.run(
                ["python", "rebalance.py", str(token_id)],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"✅ NFT {token_id} リバランス成功")

                # 古いNFTを追跡リストから削除
                if token_id in self.tracked_nfts:
                    self.tracked_nfts.remove(token_id)

                # 新しいNFT IDをトランザクションから取得
                output_lines = result.stdout.split('\n')
                new_nft_id = None
                for line in output_lines:
                    if 'new nft id:' in line.lower():
                        try:
                            new_nft_id = int(line.split(':')[-1].strip())
                            self.tracked_nfts.append(new_nft_id)
                            logger.info(f"🎯 新NFT追跡開始: {new_nft_id}")
                            break
                        except:
                            pass

                self.save_tracked_nfts()

                # JSONログ追加 - 成功
                if new_nft_id:
                    JSONLogger.log_to_json("rebalance_result", {
                        "old_nft_id": token_id,
                        "new_nft_id": new_nft_id,
                        "success": True
                    })

            else:
                logger.error(f"❌ NFT {token_id} リバランス失敗: {result.stderr}")

                # JSONログ追加 - 失敗
                JSONLogger.log_to_json("rebalance_result", {
                    "old_nft_id": token_id,
                    "new_nft_id": None,
                    "success": False,
                    "error": result.stderr[:500] if result.stderr else "Unknown error"
                })

        except subprocess.TimeoutExpired:
            logger.error(f"❌ NFT {token_id} リバランスタイムアウト")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="rebalance_position",
                message=f"Rebalance timeout for NFT {token_id}",
                error_details="Execution exceeded 120 seconds"
            )
        except Exception as e:
            logger.error(f"❌ NFT {token_id} リバランスエラー: {e}")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="rebalance_position",
                message=f"Rebalance error for NFT {token_id}",
                error_details=str(e)
            )

def main():
    print("=== 🤖 LP自動リバランス監視システム（資金最大化対応版） ===")
    print("🎯 目標: 24/7無人LP最適化")
    print("🛡️ 機能: レンジ外自動検知・リバランス")
    print("🚀 新機能: 完全自動NFT検出（10,000ブロック対応）")
    print("💰 新機能: 95%資金活用・自動SWAP計算")
    print("💵 新機能: 増資自動検知・リバランス")
    print("⏰ 開始中...")

    # 設定確認
    if not all([RPC_URL, WALLET_ADDRESS, PRIVATE_KEY]):
        logger.error("❌ 環境変数が不完全です")
        return

    logger.info("🚀 LP自動リバランス監視システム開始")
    logger.info(f"📊 監視間隔: {MONITORING_INTERVAL}秒")
    logger.info(f"🎯 リバランス閾値: {REBALANCE_THRESHOLD}")
    logger.info(f"💰 資金投入率: {TARGET_INVESTMENT_RATIO * 100}%（5%安全マージン）")
    logger.info(f"💵 増資検知閾値: ${10.0}")

    try:
        # Web3接続
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            logger.error("❌ Web3接続失敗")
            return

        chain_id = w3.eth.chain_id
        logger.info(f"✅ Web3接続成功 (Chain ID: {chain_id})")

        # プール接続確認
        pool = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
        try:
            pool.functions.slot0().call()
            logger.info(f"✅ プール確認完了: {POOL_ADDRESS}")
        except Exception as e:
            logger.error(f"❌ プール接続失敗: {e}")
            return

        # ウォレット確認
        logger.info(f"✅ ウォレット設定完了: {WALLET_ADDRESS}")

        # LPManager初期化
        lp_manager = LPManager(w3, POOL_ADDRESS, POSITION_MANAGER_ADDRESS)

        # 追跡NFT読み込み
        lp_manager.load_tracked_nfts()

        logger.info("✅ 資金最大化LP検知システム初期化完了")

        # JSONログ追加 - システム開始
        JSONLogger.log_system(
            log_level="INFO",
            function_name="main",
            message="LP monitoring system started",
            execution_time_ms=None,
            error_details=None
        )

        # 監視ループ
        cycle_count = 0
        while True:
            cycle_count += 1
            logger.info(f"\n=== 監視サイクル {cycle_count} ===")

            # JSONログ追加 - サイクル開始
            JSONLogger.log_to_json("monitoring_cycle", {
                "cycle": cycle_count,
                "timestamp": time.time(),
                "tracked_nfts": lp_manager.tracked_nfts,
                "status": "started"
            })

            try:
                lp_manager.check_and_rebalance_if_needed()
            except Exception as e:
                logger.error(f"❌ 監視サイクルエラー: {e}")
                # JSONログ追加 - エラー
                JSONLogger.log_system(
                    log_level="ERROR",
                    function_name="main",
                    message=f"Monitoring cycle {cycle_count} error",
                    error_details=str(e)
                )

            time.sleep(MONITORING_INTERVAL)

    except KeyboardInterrupt:
        logger.info("🛑 監視システム停止（ユーザー中断）")
        # JSONログ追加 - システム停止
        JSONLogger.log_system(
            log_level="INFO",
            function_name="main",
            message="System stopped by user interrupt"
        )
    except Exception as e:
        logger.error(f"❌ システムエラー: {e}")
        # JSONログ追加
        JSONLogger.log_system(
            log_level="ERROR",
            function_name="main",
            message="System error",
            error_details=str(e)
        )

if __name__ == "__main__":
    main()