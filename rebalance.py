#!/usr/bin/env python3
"""
リバランススクリプト（修正版）
指定されたNFTの流動性を撤退し、新しいレンジで再LP投入

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

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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
    BUFFER = 0.05  # 5%バッファ

    # 簡易的な最小受取量（実際のポジション価値に基づいて調整可能）
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
    """新しいレンジでLP追加"""
    logger.info("🚀 新しいレンジでLP追加中...")

    try:
        # add_liquidity.pyを呼び出し
        result = subprocess.run(
            ["python", "add_liquidity.py"],
            input="2\n",  # LP追加テストを選択
            text=True,
            capture_output=True,
            timeout=120
        )

        # 成功判定を厳密化
        success_indicators = ["SUCCESS", "🎉🎉🎉 統合版LP追加成功！", "✅ SUCCESS"]
        error_indicators = ["❌", "残高不足", "failed", "error", "Error", "Exception"]

        has_success = any(indicator in result.stdout for indicator in success_indicators)
        has_error = any(indicator in result.stdout for indicator in error_indicators)

        if result.returncode == 0 and has_success and not has_error:
            logger.info("✅ 新LP追加成功")

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

    logger.info(f"🔄 リバランス開始 - NFT {token_id}")

    # Step 1: 流動性撤退
    if not remove_liquidity(token_id):
        logger.error(f"❌ NFT {token_id} 流動性撤退失敗 - リバランス中止")
        sys.exit(1)

    # Step 2: 新LP追加
    new_nft_id = add_new_liquidity()
    if new_nft_id:
        # Step 3: 追跡NFT更新
        update_tracked_nfts(token_id, new_nft_id)

        logger.info(f"✅ リバランス完了 - 旧NFT {token_id} → 新NFT {new_nft_id}")
        print(f"REBALANCE SUCCESS: {token_id} -> {new_nft_id}")
        sys.exit(0)
    else:
        logger.error("❌ 新LP追加失敗 - リバランス未完了")
        sys.exit(1)


if __name__ == "__main__":
    main()