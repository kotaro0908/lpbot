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
from uniswap_utils import get_liquidity, decrease_liquidity, collect_fees, multicall_decrease_and_collect, \
    get_position_info
from json_logger import JSONLogger

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


def remove_liquidity(token_id):
    """流動性撤退（Multicall版）"""
    logger.info(f"🔄 NFT {token_id} の流動性撤退開始...")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    wallet = w3.eth.account.from_key(PRIVATE_KEY)

    # 現在の流動性確認
    liquidity = get_liquidity(w3, token_id)
    logger.info(f"📊 流動性確認 - NFT {token_id}: {liquidity}")

    # ポジション情報取得（ログ用）- JSONログ用追加
    position_info = None
    try:
        position_info = get_position_info(w3, token_id)
    except:
        pass  # エラーは無視

    if liquidity == 0:
        logger.warning(f"⚠️ NFT {token_id}: 流動性が既に0です")
        logger.info("💰 手数料回収を試行中...")

        # 流動性0でもcollectを試行（手数料回収のため）
        try:
            tx_hash = collect_fees(w3, wallet, token_id, GAS, GAS_PRICE)
            logger.info(f"collect sent: {w3.to_hex(tx_hash)}")

            # JSONログ追加
            JSONLogger.log_to_json("fee_collection", {
                "nft_id": token_id,
                "tx_hash": w3.to_hex(tx_hash),
                "success": True
            })

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                logger.info(f"✅ collect Tx confirmed in block: {receipt.blockNumber}")
                return True
            else:
                logger.error("❌ collect Tx failed at block level")
                return False
        except Exception as e:
            logger.error(f"❌ collect Tx exception: {e}")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="remove_liquidity",
                message="Collect failed",
                error_details=str(e)
            )
            return False

    # 全流動性撤退
    WITHDRAW_PCT = 1.0
    liquidity_to_remove = int(liquidity * WITHDRAW_PCT)
    logger.info(f"📉 撤退する流動性: {liquidity_to_remove}")

    # 最小受取量設定（バッファ込み）
    AMOUNT0_MIN = 0  # 最小ETH受取（安全のため0に設定）
    AMOUNT1_MIN = 0  # 最小USDC受取（安全のため0に設定）

    logger.info(f"📊 最小受取設定 - WETH: {AMOUNT0_MIN}, USDC: {AMOUNT1_MIN}")

    try:
        # Multicall実行（decreaseLiquidity + collect を同時実行）
        logger.info("🔄 Multicall実行中（decreaseLiquidity + collect）...")

        # JSONログ追加 - 開始時
        if position_info:
            JSONLogger.log_rebalance(
                reason="liquidity_removal_start",
                old_nft_id=token_id,
                new_nft_id=None,
                old_tick_lower=position_info.get('tick_lower'),
                old_tick_upper=position_info.get('tick_upper'),
                success=True
            )

        tx_hash = multicall_decrease_and_collect(
            w3,
            wallet,
            token_id,
            liquidity_to_remove,
            AMOUNT0_MIN,
            AMOUNT1_MIN,
            GAS,
            GAS_PRICE
        )
        logger.info(f"📝 Multicall送信: {w3.to_hex(tx_hash)}")

        # JSONログ追加 - 実行後
        JSONLogger.log_rebalance(
            reason="multicall_execution",
            old_nft_id=token_id,
            new_nft_id=None,
            old_tick_lower=position_info.get('tick_lower') if position_info else None,
            old_tick_upper=position_info.get('tick_upper') if position_info else None,
            tx_hash=w3.to_hex(tx_hash),
            success=True
        )

        # トランザクション確認
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            logger.info(f"✅ Multicall確認済み - ブロック: {receipt.blockNumber}")
            logger.info(f"✅ NFT {token_id} 流動性撤退完了")
            return True
        else:
            logger.error("❌ Multicall失敗")
            # JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="remove_liquidity",
                message="Multicall transaction failed",
                error_details=f"NFT: {token_id}, tx_hash: {w3.to_hex(tx_hash)}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ 流動性撤退エラー: {e}")
        # JSONログ追加
        JSONLogger.log_system(
            log_level="ERROR",
            function_name="remove_liquidity",
            message="Multicall execution error",
            error_details=str(e)
        )
        return False


def add_new_liquidity(old_nft_id, old_position_info):
    """新しいレンジで最大投入額LP追加"""
    logger.info("🚀 新しいレンジで最大投入額LP追加中...")

    try:
        # Web3接続
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        wallet = w3.eth.account.from_key(PRIVATE_KEY)

        # ===== 環境変数で旧ポジション情報を伝達 =====
        if old_nft_id:
            os.environ['REBALANCE_OLD_NFT_ID'] = str(old_nft_id)
        if old_position_info:
            os.environ['REBALANCE_OLD_TICK_LOWER'] = str(old_position_info.get('tick_lower', ''))
            os.environ['REBALANCE_OLD_TICK_UPPER'] = str(old_position_info.get('tick_upper', ''))

        # SWAP実行フラグをリセット
        os.environ['REBALANCE_SWAP_EXECUTED'] = 'false'
        # ===== ここまで環境変数設定 =====

        # 最適投入額計算
        optimal_amounts = calculate_optimal_amounts(w3, wallet.address)

        # レンジ情報読み込み（新レンジ記録用）
        new_tick_lower = None
        new_tick_upper = None
        try:
            with open('range_config.json', 'r') as f:
                range_config = json.load(f)
                new_tick_lower = range_config.get('lower_tick')
                new_tick_upper = range_config.get('upper_tick')
        except:
            logger.warning("⚠️ range_config.json読み込み失敗")

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

        # NFT ID取得を最優先にする成功判定
        if result.returncode == 0:
            # NFT ID抽出を先に実行
            new_nft_id = None
            output_lines = result.stdout.split('\n')

            for line in output_lines:
                # NFT ID抽出（🎯 新NFT ID: パターンを最優先）
                if '🎯 新NFT ID:' in line:
                    try:
                        import re
                        numbers = re.findall(r'\d+', line)
                        for num in numbers:
                            if len(num) >= 6 and len(num) <= 8:  # NFT IDの範囲
                                new_nft_id = int(num)
                                break
                        if new_nft_id:
                            break
                    except:
                        pass

                # フォールバック: 他のパターンも確認
                if new_nft_id is None and any(
                        keyword in line.lower() for keyword in ['nft id:', 'token id:', 'mint:', 'created nft']):
                    try:
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            for num in numbers:
                                if len(num) >= 6 and len(num) <= 8:
                                    new_nft_id = int(num)
                                    break
                    except:
                        pass

            # actual_amount抽出（追加）
            actual_amount = None
            for line in output_lines:
                if '投入予定:' in line:
                    try:
                        import re
                        # "投入予定: 0.011152 WETH, 42.03 USDC" のパターンを解析
                        numbers = re.findall(r'[\d.]+', line)
                        if len(numbers) >= 2:
                            weth_amount = float(numbers[0])
                            usdc_amount = float(numbers[1])
                            # ETH価格から概算
                            eth_price = optimal_amounts.get('eth_price', 3800)
                            actual_amount = (weth_amount * eth_price) + usdc_amount
                    except:
                        pass

            # NFT IDが取得できたら成功
            if new_nft_id:
                logger.info("✅ 最大投入額での新LP追加成功")
                logger.info(f"🎯 新NFT ID: {new_nft_id}")
                logger.info(f"💰 投入額: ${optimal_amounts['total_investment_usd']:.2f}")
                print(f"🎯 新NFT ID: {new_nft_id}")  # main.pyが検知用

                # トランザクションハッシュも抽出（ログ用）
                tx_hash = None
                for line in output_lines:
                    if 'transaction hash:' in line.lower():
                        tx_hash = line.split(':')[-1].strip()
                        break
                    elif line.startswith('0x') and len(line) == 66:
                        tx_hash = line.strip()
                        break

                if tx_hash:
                    logger.info(f"📝 新LP追加Tx: {tx_hash}")

                # SWAP実行状態を確認
                swap_executed = os.environ.get('REBALANCE_SWAP_EXECUTED', 'false') == 'true'

                # 成功ログ - JSONログ追加（修正版）
                JSONLogger.log_rebalance(
                    reason="range_out",  # TODO: main.pyから渡す
                    old_nft_id=old_nft_id,
                    new_nft_id=new_nft_id,
                    old_tick_lower=old_position_info.get('tick_lower') if old_position_info else None,
                    old_tick_upper=old_position_info.get('tick_upper') if old_position_info else None,
                    new_tick_lower=new_tick_lower,
                    new_tick_upper=new_tick_upper,
                    price_at_rebalance=optimal_amounts.get('eth_price'),
                    estimated_amount=optimal_amounts['total_investment_usd'],
                    actual_amount=actual_amount,  # 追加
                    swap_executed=swap_executed,
                    tx_hash=tx_hash,
                    success=True
                )

                return new_nft_id
            else:
                logger.error("❌ 新LP追加失敗 - NFT ID取得失敗")
                logger.error(f"詳細出力: {result.stdout}")
                logger.error(f"エラー出力: {result.stderr}")

                # 失敗ログ - JSONログ追加
                JSONLogger.log_rebalance(
                    reason="range_out",
                    old_nft_id=old_nft_id,
                    new_nft_id=None,
                    old_tick_lower=old_position_info.get('tick_lower') if old_position_info else None,
                    old_tick_upper=old_position_info.get('tick_upper') if old_position_info else None,
                    estimated_amount=optimal_amounts['total_investment_usd'],
                    error_message="NFT ID extraction failed",
                    success=False
                )

                return None
        else:
            logger.error(f"❌ 新LP追加失敗 - Return Code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")

            # システムエラーログ - JSONログ追加
            JSONLogger.log_system(
                log_level="ERROR",
                function_name="add_new_liquidity",
                message=f"add_liquidity.py failed with code {result.returncode}",
                error_details=result.stderr[:500] if result.stderr else "No error output"
            )

            return None

    except Exception as e:
        # JSONLoggerエラーでも新NFT IDがあれば返す
        if 'new_nft_id' in locals() and new_nft_id:
            logger.warning(f"⚠️ ログエラーが発生しましたが、新NFT {new_nft_id} は作成されました: {e}")
            return new_nft_id
        else:
            # TimeoutErrorとその他のエラーを判別
            if isinstance(e, subprocess.TimeoutExpired):

                logger.error("❌ 新LP追加タイムアウト")
                JSONLogger.log_system(
                    log_level="ERROR",
                    function_name="add_new_liquidity",
                    message="add_liquidity.py timeout",
                    error_details="Execution exceeded 180 seconds"
                )
            else:
                logger.error(f"❌ 新LP追加エラー: {e}")
                JSONLogger.log_system(
                    log_level="ERROR",
                    function_name="add_new_liquidity",
                    message="Unexpected error in LP addition",
                    error_details=str(e)
                )
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

    # Step 0: リバランス開始時の旧ポジション情報を取得
    old_position_info = None
    w3 = None
    optimal_amounts = None  # スコープ問題解決
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        old_position_info = get_position_info(w3, token_id)
        if old_position_info:
            logger.info(
                f"📊 旧ポジション情報取得: tick範囲 [{old_position_info.get('tick_lower')}, {old_position_info.get('tick_upper')}]")
    except Exception as e:
        logger.warning(f"⚠️ 旧ポジション情報取得失敗: {e}")
    # ===== ここまで追加 =====

    # リバランス開始ログ - JSONログ追加
    JSONLogger.log_system(
        log_level="INFO",
        function_name="main",
        message=f"Rebalance started for NFT {token_id}"
    )

    # Step 1: 流動性撤退
    if not remove_liquidity(token_id):
        logger.error(f"❌ NFT {token_id} 流動性撤退失敗 - リバランス中止")
        sys.exit(1)

    # Step 2: 最大投入額での新LP追加
    new_nft_id = add_new_liquidity(token_id, old_position_info)  # 引数追加

    if new_nft_id:
        # optimal_amounts取得のため再計算
        optimal_amounts = None
        if w3:
            wallet = w3.eth.account.from_key(PRIVATE_KEY)
            optimal_amounts = calculate_optimal_amounts(w3, wallet.address)

        # Step 3: 追跡NFT更新（既存のコード）
        update_tracked_nfts(token_id, new_nft_id)

        logger.info(f"✅ 完全リバランス完了 - 旧NFT {token_id} → 新NFT {new_nft_id}")
        logger.info("🚀 最大投入額での効率的なリバランスが完了しました")

        # ===== ここから追加（統合ログ） =====
        # 統合リバランスログ出力
        new_tick_lower = None
        new_tick_upper = None
        try:
            with open('range_config.json', 'r') as f:
                range_config = json.load(f)
                new_tick_lower = range_config.get('lower_tick')
                new_tick_upper = range_config.get('upper_tick')
        except:
            pass

        # 価格情報取得
        eth_price = None
        if w3:
            eth_price = get_eth_price(w3)

        # 統合ログ出力
        JSONLogger.log_rebalance(
            reason="range_out",  # TODO: main.pyから理由を受け取る
            old_nft_id=token_id,
            new_nft_id=new_nft_id,
            old_tick_lower=old_position_info.get('tick_lower') if old_position_info else None,
            old_tick_upper=old_position_info.get('tick_upper') if old_position_info else None,
            new_tick_lower=new_tick_lower,
            new_tick_upper=new_tick_upper,
            price_at_rebalance=eth_price,
            estimated_amount=optimal_amounts.get('total_investment_usd') if optimal_amounts else None,
            swap_executed=os.environ.get('REBALANCE_SWAP_EXECUTED', 'false') == 'true',
            tx_hash=None,  # multicallのため個別ログで記録
            success=True
        )
        # ===== ここまで追加 =====

        # 完了ログ - JSONログ追加
        JSONLogger.log_system(
            log_level="INFO",
            function_name="main",
            message=f"Rebalance completed: {token_id} -> {new_nft_id}"
        )

        print(f"REBALANCE SUCCESS: {token_id} -> {new_nft_id}")
        sys.exit(0)
    else:
        logger.error("❌ 新LP追加失敗 - リバランス未完了")
        sys.exit(1)


if __name__ == "__main__":
    main()