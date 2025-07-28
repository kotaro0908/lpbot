#!/usr/bin/env python3
"""
リバランススクリプト（完全修正版 - 最適投入額計算移植）
指定されたNFTの流動性を撤退し、新しいレンジで最大投入額再LP投入

使用方法:
python rebalance.py <NFT_ID>
"""

import os
import sys
import time
import json
import subprocess
import logging
from web3 import Web3
from dotenv import load_dotenv
from uniswap_utils import get_liquidity, decrease_liquidity, collect_fees

# .envファイルを読み込み
load_dotenv()

# 設定
RPC_URL = os.getenv('RPC_URL')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
GAS = int(os.getenv('GAS', 5000000))
GAS_PRICE = int(os.getenv('GAS_PRICE', 2000000000))

# 追加: 最適投入額計算用設定
USDC_ADDRESS = os.getenv('USDC_ADDRESS')
WETH_ADDRESS = os.getenv('WETH_ADDRESS')
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"
FUND_UTILIZATION_RATE = float(os.getenv('FUND_UTILIZATION_RATE', 0.95))  # 95%
GAS_BUFFER_ETH = float(os.getenv('GAS_BUFFER_ETH', 0.005))  # ガスバッファ

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}
]

POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_token_balance(w3, token_address, wallet_address):
    """トークン残高取得"""
    # チェックサムアドレスに変換
    token_address = w3.to_checksum_address(token_address)
    wallet_address = w3.to_checksum_address(wallet_address)
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return token_contract.functions.balanceOf(wallet_address).call()


def get_eth_price(w3):
    """ETH価格取得（Pool contractから）"""
    try:
        # チェックサムアドレスに変換
        pool_address = w3.to_checksum_address(POOL_ADDRESS)
        pool_contract = w3.eth.contract(address=pool_address, abi=POOL_ABI)
        slot0 = pool_contract.functions.slot0().call()
        sqrt_price_x96 = slot0[0]
        price_raw = (sqrt_price_x96 / (2 ** 96)) ** 2
        eth_price = price_raw * (10 ** 12)  # USDC per WETH

        if eth_price <= 0:
            logger.warning("⚠️ Pool価格取得失敗 - フォールバック価格使用")
            return 3900.0

        logger.info(f"📊 ETH価格: ${eth_price:.2f}")
        return float(eth_price)
    except Exception as e:
        logger.warning(f"⚠️ ETH価格取得エラー - フォールバック価格使用: {e}")
        return 3900.0


def calculate_optimal_amounts(w3, wallet_address):
    """最適投入額計算（main.pyから移植）"""
    logger.info("💰 最適投入額計算中...")

    # チェックサムアドレスに変換
    wallet_address = w3.to_checksum_address(wallet_address)
    weth_address = w3.to_checksum_address(WETH_ADDRESS)
    usdc_address = w3.to_checksum_address(USDC_ADDRESS)

    # 残高取得
    eth_balance = w3.eth.get_balance(wallet_address)
    weth_balance = get_token_balance(w3, weth_address, wallet_address)
    usdc_balance = get_token_balance(w3, usdc_address, wallet_address)

    eth_amount = eth_balance / 10 ** 18
    weth_amount = weth_balance / 10 ** 18
    usdc_amount = usdc_balance / 10 ** 6

    logger.info(f"📊 現在残高:")
    logger.info(f"   ETH: {eth_amount:.6f}")
    logger.info(f"   WETH: {weth_amount:.6f}")
    logger.info(f"   USDC: {usdc_amount:.2f}")

    # 利用可能資金計算
    usable_eth = max(0, eth_amount - GAS_BUFFER_ETH)
    total_eth_value = usable_eth + weth_amount
    total_usdc_value = usdc_amount

    # ETH価格取得
    eth_price = get_eth_price(w3)

    # 総資産価値計算（USD）
    total_eth_usd = total_eth_value * eth_price
    total_usdc_usd = total_usdc_value
    total_value_usd = total_eth_usd + total_usdc_usd

    # 運用可能額計算（95%活用）
    available_for_investment_usd = total_value_usd * FUND_UTILIZATION_RATE

    logger.info(f"📊 資産分析:")
    logger.info(f"   総ETH価値: ${total_eth_usd:.2f}")
    logger.info(f"   総USDC価値: ${total_usdc_usd:.2f}")
    logger.info(f"   総資産価値: ${total_value_usd:.2f}")
    logger.info(f"   運用可能額: ${available_for_investment_usd:.2f}")

    # 50:50分散で最適投入額計算
    target_eth_usd = available_for_investment_usd / 2
    target_usdc_usd = available_for_investment_usd / 2

    final_eth_amount = target_eth_usd / eth_price
    final_usdc_amount = target_usdc_usd

    # SWAP必要性判定
    current_eth_usd = total_eth_value * eth_price
    current_usdc_usd = total_usdc_value

    needs_swap = False
    swap_direction = None
    swap_amount = 0

    if current_eth_usd > target_eth_usd:
        # ETH過多 → ETH→USDC SWAP
        excess_eth_usd = current_eth_usd - target_eth_usd
        if excess_eth_usd > 1.0:  # 1USD以上の差があればSWAP
            needs_swap = True
            swap_direction = "ETH_TO_USDC"
            swap_amount = excess_eth_usd
    elif current_usdc_usd > target_usdc_usd:
        # USDC過多 → USDC→ETH SWAP
        excess_usdc_usd = current_usdc_usd - target_usdc_usd
        if excess_usdc_usd > 1.0:  # 1USD以上の差があればSWAP
            needs_swap = True
            swap_direction = "USDC_TO_ETH"
            swap_amount = excess_usdc_usd

    optimal_amounts = {
        'needs_swap': needs_swap,
        'swap_direction': swap_direction,
        'swap_amount': swap_amount,
        'final_eth_amount': final_eth_amount,
        'final_usdc_amount': final_usdc_amount,
        'total_investment_usd': available_for_investment_usd,
        'eth_price': eth_price
    }

    logger.info(f"📊 最適投入額: ${available_for_investment_usd:.2f}")
    logger.info(f"   ETH: {final_eth_amount:.6f}")
    logger.info(f"   USDC: {final_usdc_amount:.2f}")

    if needs_swap:
        logger.info(f"🔄 SWAP必要: {swap_direction}")
        logger.info(f"   SWAP額: ${swap_amount:.2f}")
    else:
        logger.info("✅ SWAP不要")

    return optimal_amounts


def safe_collect(w3, wallet, token_id):
    """collectのnonceずれ・二重送信対策。何度でも実行OKな構成"""
    try:
        # 最新nonceで送信（状態変化後に確実に回収できるように）
        tx_hash2 = collect_fees(
            w3,
            wallet,
            token_id,
            GAS,
            GAS_PRICE
        )
        logger.info(f"collect sent: {w3.to_hex(tx_hash2)}")
        receipt2 = w3.eth.wait_for_transaction_receipt(tx_hash2)
        if receipt2.status == 1:
            logger.info(f"✅ collect Tx confirmed in block: {receipt2.blockNumber}")
            return True
        else:
            logger.error("❌ collect Tx failed at block level。未回収残高があるかも")
            return False
    except Exception as e:
        # 既にfee回収済み/残高なしならこのエラーもOK
        if "already been used" in str(e) or "revert" in str(e):
            logger.warning("⚠️ collect Tx: 既にfee回収済み、または残高なしの可能性")
            return True
        else:
            logger.error(f"❌ collect Tx exception: {e}")
            return False


def remove_liquidity(token_id):
    """流動性撤退"""
    logger.info(f"🔄 NFT {token_id} の流動性撤退開始...")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    wallet = w3.eth.account.from_key(PRIVATE_KEY)

    # 現在の流動性確認
    liquidity = get_liquidity(w3, token_id)
    logger.info(f"📊 流動性確認 - NFT {token_id}: {liquidity}")

    if liquidity == 0:
        logger.warning(f"⚠️ NFT {token_id}: 流動性が既に0です")
        # 流動性0でもcollectを試行（手数料回収のため）
        logger.info("💰 手数料回収を試行中...")
        safe_collect(w3, wallet, token_id)
        return True

    # 全流動性撤退
    WITHDRAW_PCT = 1.0
    liquidity_to_remove = int(liquidity * WITHDRAW_PCT)
    logger.info(f"📉 撤退する流動性: {liquidity_to_remove}")

    # 最小受取量設定（バッファ込み）
    AMOUNT0_MIN = 0  # 最小ETH受取（安全のため0に設定）
    AMOUNT1_MIN = 0  # 最小USDC受取（安全のため0に設定）

    logger.info(f"📊 最小受取設定 - WETH: {AMOUNT0_MIN}, USDC: {AMOUNT1_MIN}")

    try:
        # decreaseLiquidity実行
        logger.info("🔽 decreaseLiquidity実行中...")
        tx_hash = decrease_liquidity(
            w3,
            wallet,
            token_id,
            liquidity_to_remove,
            AMOUNT0_MIN,
            AMOUNT1_MIN,
            GAS,
            GAS_PRICE
        )
        logger.info(f"📝 decreaseLiquidity送信: {w3.to_hex(tx_hash)}")

        # トランザクション確認
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            logger.info(f"✅ decreaseLiquidity確認済み - ブロック: {receipt.blockNumber}")
        else:
            logger.error("❌ decreaseLiquidity失敗")
            return False

        # collect実行
        logger.info("💰 手数料・残高回収中...")
        collect_success = safe_collect(w3, wallet, token_id)

        if collect_success:
            logger.info(f"✅ NFT {token_id} 流動性撤退完了")
            return True
        else:
            logger.error(f"❌ NFT {token_id} collect失敗 - 撤退未完了")
            return False

    except Exception as e:
        logger.error(f"❌ 流動性撤退エラー: {e}")
        return False


def add_new_liquidity():
    """新しいレンジで最大投入額LP追加"""
    logger.info("🚀 新しいレンジで最大投入額LP追加中...")

    try:
        # Web3接続
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        wallet = w3.eth.account.from_key(PRIVATE_KEY)

        # 最適投入額計算
        optimal_amounts = calculate_optimal_amounts(w3, wallet.address)

        # add_liquidity.pyを最適化引数付きで呼び出し
        cmd = [
            "python", "add_liquidity.py",
            "--eth", str(optimal_amounts['final_eth_amount']),
            "--usdc", str(optimal_amounts['final_usdc_amount']),
            "--auto"
        ]

        logger.info(f"🔧 add_liquidity.py実行: {' '.join(cmd[2:])}")  # 引数部分のみ表示

        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=180  # タイムアウト延長（SWAP含むため）
        )

        # 成功判定を厳密化
        success_indicators = ["SUCCESS", "🎉🎉🎉 統合版LP追加成功！", "✅ SUCCESS"]
        error_indicators = ["❌", "残高不足", "failed", "error", "Error", "Exception"]

        has_success = any(indicator in result.stdout for indicator in success_indicators)
        has_error = any(indicator in result.stdout for indicator in error_indicators)

        if result.returncode == 0 and has_success and not has_error:
            logger.info("✅ 最大投入額での新LP追加成功")

            # 出力からトランザクションハッシュ・NFT IDを抽出
            output_lines = result.stdout.split('\n')
            tx_hash = None
            new_nft_id = None

            for line in output_lines:
                # トランザクションハッシュ抽出
                if 'transaction hash:' in line.lower() or 'tx hash:' in line.lower():
                    tx_hash = line.split(':')[-1].strip()
                elif line.startswith('0x') and len(line) == 66:
                    tx_hash = line.strip()

                # NFT ID抽出（複数パターン対応）
                if any(keyword in line.lower() for keyword in ['nft id:', 'token id:', 'mint:', 'created nft']):
                    try:
                        # 数字を抽出
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            # 7桁の数字（NFT IDらしきもの）を探す
                            for num in numbers:
                                if len(num) >= 6 and len(num) <= 8:  # NFT IDの範囲
                                    new_nft_id = int(num)
                                    break
                    except:
                        pass

            if tx_hash:
                logger.info(f"📝 新LP追加Tx: {tx_hash}")

            if new_nft_id:
                logger.info(f"🎯 新NFT ID: {new_nft_id}")
                logger.info(f"💰 投入額: ${optimal_amounts['total_investment_usd']:.2f}")
                print(f"🎯 新NFT ID: {new_nft_id}")  # main.pyが検知用
                return new_nft_id
            else:
                logger.warning("⚠️ 新NFT ID取得失敗")
                return None

        elif result.returncode == 0:
            logger.error("❌ 新LP追加実行したが実際は失敗")
            logger.error(f"詳細出力: {result.stdout}")
            logger.error(f"エラー出力: {result.stderr}")
            return None
        else:
            logger.error(f"❌ 新LP追加失敗 - Return Code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("❌ 新LP追加タイムアウト")
        return None
    except Exception as e:
        logger.error(f"❌ 新LP追加エラー: {e}")
        return None


def update_tracked_nfts(old_nft_id, new_nft_id):
    """追跡NFTファイル更新"""
    try:
        tracked_file = "tracked_nfts.json"

        if os.path.exists(tracked_file):
            with open(tracked_file, 'r') as f:
                data = json.load(f)
        else:
            data = {"nft_ids": []}

        # 古いIDを削除
        if old_nft_id in data["nft_ids"]:
            data["nft_ids"].remove(old_nft_id)
            logger.info(f"📝 追跡リストから削除: NFT {old_nft_id}")

        # 新しいIDを追加
        if new_nft_id and new_nft_id not in data["nft_ids"]:
            data["nft_ids"].append(new_nft_id)
            logger.info(f"📝 追跡リストに追加: NFT {new_nft_id}")

        # ファイル保存
        with open(tracked_file, 'w') as f:
            json.dump(data, f)

        logger.info(f"💾 追跡NFT更新完了: {data['nft_ids']}")
        return True

    except Exception as e:
        logger.error(f"❌ 追跡NFT更新失敗: {e}")
        return False


def main():
    """メイン実行関数"""
    if len(sys.argv) != 2:
        print("使用方法: python rebalance.py <NFT_ID>")
        sys.exit(1)

    try:
        token_id = int(sys.argv[1])
    except ValueError:
        print("エラー: NFT_IDは数値で指定してください")
        sys.exit(1)

    logger.info(f"🔄 完全リバランス開始 - NFT {token_id}")
    logger.info("💰 最大投入額での資金効率最適化リバランス")

    # Step 1: 流動性撤退
    if not remove_liquidity(token_id):
        logger.error(f"❌ NFT {token_id} 流動性撤退失敗 - リバランス中止")
        sys.exit(1)

    # Step 2: 最大投入額での新LP追加
    new_nft_id = add_new_liquidity()
    if new_nft_id:
        # Step 3: 追跡NFT更新
        update_tracked_nfts(token_id, new_nft_id)

        logger.info(f"✅ 完全リバランス完了 - 旧NFT {token_id} → 新NFT {new_nft_id}")
        logger.info("🚀 最大投入額での効率的なリバランスが完了しました")
        print(f"REBALANCE SUCCESS: {token_id} -> {new_nft_id}")
        sys.exit(0)
    else:
        logger.error("❌ 新LP追加失敗 - リバランス未完了")
        sys.exit(1)


if __name__ == "__main__":
    main()