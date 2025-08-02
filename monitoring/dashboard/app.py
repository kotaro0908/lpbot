from dotenv import load_dotenv

load_dotenv("/root/lpbot/.env")
load_dotenv("/root/lpbot/.env.secret")

# monitoring/dashboard/app.py
import math
from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import json
import os
import sys
import requests
from web3 import Web3

# プロジェクトルートをパスに追加
sys.path.append('/root/lpbot')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# データベースパス
DB_PATH = '/root/lpbot/monitoring/lpbot.db'

# 既存のWeb3設定を使用
RPC_URL = os.getenv("RPC_URL", "https://arb1.arbitrum.io/rpc")
WETH_ADDRESS = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
POOL_ADDRESS = "0xC6962004f452bE9203591991D15f6b388e09E8D0"

# The Graph API設定
GRAPH_API_URL = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-arbitrum"

# Web3接続
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# ERC20 ABI（残高取得用）
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def calculate_il_loss(nft_id, price_at_entry, actual_amount):
    """正確なIL計算を実行"""
    try:
        conn = get_db_connection()
        
        # このNFTの exit_price を取得（次のリバランス時の価格）
        exit_data = conn.execute("""
            SELECT price_at_rebalance as exit_price
            FROM rebalance_history
            WHERE old_nft_id = ? AND reason = 'range_out' AND success = 1
            ORDER BY timestamp ASC LIMIT 1
        """, (nft_id,)).fetchone()
        
        conn.close()
        
        if not exit_data or not exit_data['exit_price']:
            return 0  # exit価格がない場合は0
        
        exit_price = float(exit_data['exit_price'])
        entry_price = float(price_at_entry)
        amount = float(actual_amount)
        
        # IL計算: 2 * sqrt(price_ratio) / (1 + price_ratio) - 1
        price_ratio = exit_price / entry_price
        sqrt_ratio = (price_ratio ** 0.5)
        il_percentage = 2 * sqrt_ratio / (1 + price_ratio) - 1
        il_amount = abs(il_percentage * amount)
        
        return il_amount
        
    except Exception as e:
        print(f"IL計算エラー: {e}")
        return 0


def get_db_connection():
    """データベース接続"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """メインダッシュボード"""
    return render_template('index.html')


@app.route('/investment')
def investment():
    """投資履歴管理ページ"""
    return render_template('investment.html')


@app.route('/api/investment', methods=['GET', 'POST'])
def api_investment():
    """投資履歴API"""
    if request.method == 'POST':
        # 新規投資記録を追加
        data = request.json
        conn = get_db_connection()

        conn.execute("""
                     INSERT INTO investment_history
                         (timestamp, action, amount_usd, note)
                     VALUES (?, ?, ?, ?)
                     """, (
                         data['date'],
                         data['action'],
                         float(data['amount']),
                         data.get('note', '')
                     ))

        # 累計投資額を更新
        update_cumulative_investment(conn)
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})

    else:
        # 投資履歴を取得
        conn = get_db_connection()
        history = conn.execute("""
                               SELECT *
                               FROM investment_history
                               ORDER BY timestamp DESC
                               """).fetchall()
        conn.close()

        return jsonify([dict(row) for row in history])


def update_cumulative_investment(conn):
    """累計投資額を更新"""
    rows = conn.execute("""
                        SELECT timestamp, action, amount_usd
                        FROM investment_history
                        ORDER BY timestamp
                        """).fetchall()

    cumulative = 0
    for row in rows:
        if row['action'] == 'deposit':
            cumulative += row['amount_usd']
        elif row['action'] == 'withdraw':
            cumulative -= row['amount_usd']

        conn.execute("""
                     UPDATE investment_history
                     SET cumulative_investment = ?
                     WHERE timestamp = ? AND action = ? AND amount_usd = ?
                     """, (cumulative, row['timestamp'], row['action'], row['amount_usd']))


def ticks_to_price_range(lower_tick, upper_tick):
    """ティックを価格レンジに変換"""
    try:
        # tick to price: price = 1.0001^tick * (10^6 / 10^18)
        lower_price = math.pow(1.0001, lower_tick) * (10 ** 12)
        upper_price = math.pow(1.0001, upper_tick) * (10 ** 12)

        # レンジ幅の計算
        range_width = ((upper_price - lower_price) / ((upper_price + lower_price) / 2)) * 100

        return {
            'lower_price': lower_price,
            'upper_price': upper_price,
            'range_width_percent': range_width
        }
    except Exception as e:
        print(f"価格変換エラー: {e}")
        return {
            'lower_price': 0,
            'upper_price': 0,
            'range_width_percent': 0
        }


def calculate_in_range_percent():
    """過去24時間のレンジ内滞在率を計算"""
    # TODO: 実装が必要
    # 現在は仮の値を返す
    return 85.5  # 85.5%という意味


def format_timestamp(timestamp_str):
    """タイムスタンプを見やすい形式に変換"""
    try:
        if timestamp_str:
            # ISO形式のタイムスタンプをパース
            dt = datetime.fromisoformat(timestamp_str.replace('T', ' ').split('.')[0])
            # YYYY/MM/DD HH:MM:SS形式に変換
            return dt.strftime('%Y/%m/%d %H:%M:%S')
    except:
        pass
    return timestamp_str


@app.route('/api/dashboard_data')
def api_dashboard_data():
    """ダッシュボード用データAPI"""
    conn = get_db_connection()

    # 現在の総資産価値とウォレット情報
    eth_price = get_current_eth_price()
    balances = get_wallet_balances()
    wallet_value = (balances['eth'] + balances['weth']) * eth_price + balances['usdc']
    lp_value = 65.0  # 暫定的な固定値
    total_value = wallet_value + lp_value

    # NFT IDを取得
    current_nft = get_current_nft_id()
    print(f"API: 現在のNFT ID = {current_nft}")

    # 累計収益
    total_fees = conn.execute("""
                              SELECT COALESCE(SUM(total_usd), 0) as total
                              FROM fee_collection_history
                              """).fetchone()['total']

    # 累計ガス代
    total_gas = conn.execute("""
                             SELECT COALESCE(SUM(gas_cost_usd), 0) as total
                             FROM rebalance_history
                             """).fetchone()['total']

    # 投資額
    investment = conn.execute("""
                              SELECT COALESCE(cumulative_investment, 0) as total
                              FROM investment_history
                              ORDER BY timestamp DESC
                                  LIMIT 1
                              """).fetchone()

    total_investment = investment['total'] if investment else 0

    # 今日の収益
    today_fees = conn.execute("""
                              SELECT COALESCE(SUM(total_usd), 0) as total
                              FROM fee_collection_history
                              WHERE DATE (timestamp) = DATE ('now', 'localtime')
                              """).fetchone()['total']

    # 平均日次収益と最高日次収益
    daily_stats = conn.execute("""
                               SELECT AVG(daily_total) as avg_daily,
                                      MAX(daily_total) as max_daily
                               FROM (SELECT DATE (timestamp) as date, SUM(total_usd) as daily_total
                               FROM fee_collection_history
                               GROUP BY DATE (timestamp)
                                   )
                               """).fetchone()

    avg_daily_profit = daily_stats["avg_daily"] if daily_stats and daily_stats["avg_daily"] else 0
    max_daily_profit = daily_stats["max_daily"] if daily_stats and daily_stats["max_daily"] else 0

    # リバランス統計を追加（修正版）
    rebalance_stats = conn.execute("""
                                   SELECT COUNT(DISTINCT CASE
                                                             WHEN new_nft_id IS NOT NULL
                                                                 THEN old_nft_id || '-' || new_nft_id END)         as unique_transitions,
                                          COUNT(*)                                                                 as total_attempts,
                                          COUNT(CASE WHEN success = 1 AND new_nft_id IS NOT NULL THEN 1 END)       as success_count,
                                          COUNT(CASE WHEN DATE (timestamp) = DATE ('now', 'localtime') THEN 1 END) as today_attempts,
                                          COUNT(DISTINCT CASE WHEN new_nft_id IS NOT NULL AND DATE
                                                (timestamp, 'start of month') = DATE ('now', 'start of month') THEN
                                                old_nft_id || '-' || new_nft_id
                                                END)                                                               as month_transitions
                                   FROM rebalance_history
                                   """).fetchone()

    # 成功率計算
    success_rate = (rebalance_stats['success_count'] / rebalance_stats['total_attempts'] * 100) if rebalance_stats[
                                                                                                       'total_attempts'] > 0 else 0

    # 最新のリバランス情報を取得
    last_rebalance = conn.execute("""
                                  SELECT timestamp, new_tick_lower, new_tick_upper
                                  FROM rebalance_history
                                  WHERE success = 1 AND new_nft_id IS NOT NULL
                                  ORDER BY timestamp DESC
                                      LIMIT 1
                                  """).fetchone()

    # レンジ情報を取得（NFTのレンジ情報から）
    current_range = None
    if current_nft and last_rebalance and last_rebalance['new_tick_lower'] is not None:
        price_range = ticks_to_price_range(last_rebalance['new_tick_lower'], last_rebalance['new_tick_upper'])
        current_range = {
            'lower': last_rebalance['new_tick_lower'],
            'upper': last_rebalance['new_tick_upper'],
            'lower_price': price_range['lower_price'],
            'upper_price': price_range['upper_price'],
            'range_width_percent': price_range['range_width_percent']
        }
    else:
        # range_config.jsonから取得
        try:
            with open('/root/lpbot/range_config.json', 'r') as f:
                range_data = json.load(f)
                if 'lower_tick' in range_data and 'upper_tick' in range_data:
                    price_range = ticks_to_price_range(range_data['lower_tick'], range_data['upper_tick'])
                    current_range = {
                        'lower': range_data['lower_tick'],
                        'upper': range_data['upper_tick'],
                        'lower_price': price_range['lower_price'],
                        'upper_price': price_range['upper_price'],
                        'range_width_percent': price_range['range_width_percent']
                    }
        except Exception as e:
            print(f"レンジ情報取得エラー: {e}")

    # レンジ内滞在率を計算
    in_range_percent = calculate_in_range_percent()

    conn.close()

    # レスポンスにすべての情報を追加
    return jsonify({
        'total_value': total_value,
        'lp_value': lp_value,
        'wallet_value': wallet_value,
        'total_investment': total_investment,
        'total_fees': total_fees,
        'total_gas': total_gas,
        'net_profit': total_fees - total_gas,
        'roi': ((total_value - total_investment) / total_investment * 100) if total_investment > 0 else 0,
        'current_nft': current_nft,
        'today_fees': today_fees,
        'avg_daily_profit': avg_daily_profit,
        'max_daily_profit': max_daily_profit,
        'rebalance_today': rebalance_stats['today_attempts'] if rebalance_stats else 0,
        'rebalance_count': rebalance_stats['unique_transitions'] if rebalance_stats else 0,
        'rebalance_attempts': rebalance_stats['total_attempts'] if rebalance_stats else 0,
        'month_rebalances': rebalance_stats['month_transitions'] if rebalance_stats else 0,
        'success_rate': success_rate,
        'current_range': current_range,
        'last_rebalance': format_timestamp(last_rebalance['timestamp']) if last_rebalance else None,
        'in_range_time_percent': in_range_percent
    })


@app.route('/api/transaction_history')
def api_transaction_history():
    """取引履歴API"""
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))

    conn = get_db_connection()

    # 総取引回数を取得
    total_count_result = conn.execute("""
                                      SELECT COUNT(*) as count
                                      FROM rebalance_history
                                      WHERE reason = 'range_out' AND success = 1 AND new_nft_id IS NOT NULL
                                      """).fetchone()
    total_count = total_count_result['count'] if total_count_result else 0

    # 平均利益を計算
    avg_stats = conn.execute("""
                             SELECT AVG(CASE
                                            WHEN fc.total_usd IS NOT NULL
                                                THEN fc.total_usd - COALESCE(rh.gas_cost_usd, 0)
                                            ELSE -COALESCE(rh.gas_cost_usd, 0)
                                 END)        as avg_profit,
                                    AVG(CASE
                                            WHEN fc.total_usd IS NOT NULL AND rh.actual_amount > 0
                                                THEN
                                                ((fc.total_usd - COALESCE(rh.gas_cost_usd, 0)) / rh.actual_amount) *
                                                100
                                            ELSE 0
                                        END) as avg_profit_percent
                             FROM rebalance_history rh
                                      LEFT JOIN fee_collection_history fc ON rh.new_nft_id = fc.nft_id
                             WHERE rh.reason = 'range_out'
                               AND rh.success = 1
                               AND rh.new_nft_id IS NOT NULL
                             """).fetchone()

    avg_profit = avg_stats['avg_profit'] if avg_stats and avg_stats['avg_profit'] else 0
    avg_profit_percent = avg_stats['avg_profit_percent'] if avg_stats and avg_stats['avg_profit_percent'] else 0

    # 取引履歴を取得
    transactions = []
    rows = conn.execute("""
                        SELECT rh.timestamp,
                               rh.new_nft_id as nft_id,
                               rh.actual_amount,
                               rh.gas_cost_usd,
                               rh.price_at_rebalance,
                               fc.total_usd  as fee_revenue,
                               fc.amount0    as fee_weth,
                               fc.amount1    as fee_usdc,
                               rh.tx_hash
                        FROM rebalance_history rh
                                 LEFT JOIN fee_collection_history fc ON rh.new_nft_id = fc.nft_id
                        WHERE rh.reason = 'range_out'
                          AND rh.success = 1
                          AND rh.new_nft_id IS NOT NULL
                        ORDER BY rh.timestamp DESC LIMIT ?
                        OFFSET ?
                        """, (limit, offset)).fetchall()

    for row in rows:
        # 手数料収入（NULL対応）
        fee_revenue = float(row['fee_revenue']) if row['fee_revenue'] else 0

        # ガス代
        gas_cost = float(row['gas_cost_usd']) if row['gas_cost_usd'] else 0

        # IL損失の正確な計算
        il_loss = calculate_il_loss(row['nft_id'], row['price_at_rebalance'], row['actual_amount'])

        # 純利益
        net_profit = fee_revenue - il_loss - gas_cost

        # 利益率
        profit_percent = (net_profit / float(row['actual_amount']) * 100) if row['actual_amount'] and float(
            row['actual_amount']) > 0 else 0

        transactions.append({
            'timestamp': row['timestamp'],
            'nft_id': row['nft_id'],
            'fee_revenue': fee_revenue,
            'il_loss': il_loss,
            'gas_cost': gas_cost,
            'net_profit': net_profit,
            'profit_percent': profit_percent,
            'tx_hash': row['tx_hash']
        })

    # もっと見るボタンの表示判定
    has_more = (offset + limit) < total_count

    conn.close()

    return jsonify({
        'total_count': total_count,
        'avg_profit': avg_profit,
        'avg_profit_percent': avg_profit_percent,
        'transactions': transactions,
        'has_more': has_more
    })


def get_current_eth_price():
    """現在のETH価格を取得（プールコントラクトから直接）"""
    try:
        # Uniswap V3 USDC/WETH プール
        POOL_ADDRESS = Web3.to_checksum_address("0xC6962004f452bE9203591991D15f6b388e09E8D0")

        # Pool ABI (slot0のみ)
        pool_abi = [{
            "inputs": [],
            "name": "slot0",
            "outputs": [
                {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                {"internalType": "int24", "name": "tick", "type": "int24"}
            ],
            "stateMutability": "view",
            "type": "function"
        }]

        pool = w3.eth.contract(address=POOL_ADDRESS, abi=pool_abi)
        slot0 = pool.functions.slot0().call()
        sqrt_price_x96 = slot0[0]

        # 価格計算
        price = (sqrt_price_x96 / (2 ** 96)) ** 2
        eth_price_usd = price * (10 ** 12)  # USDC decimals adjustment

        print(f"ETH価格取得成功: ${eth_price_usd:.2f}")
        return eth_price_usd

    except Exception as e:
        print(f"ETH価格取得エラー: {e}")
        return 3800.0  # フォールバック


def get_wallet_balances():
    """ウォレット残高取得"""
    try:
        # ウォレットアドレス取得
        wallet_address = os.getenv("WALLET_ADDRESS")
        if not wallet_address:
            print("WALLET_ADDRESS環境変数が設定されていません")
            return {'eth': 0, 'weth': 0, 'usdc': 0}

        # ETH残高
        eth_balance = w3.eth.get_balance(wallet_address)
        eth_amount = eth_balance / 10 ** 18

        # WETH残高
        weth_contract = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
        weth_balance = weth_contract.functions.balanceOf(wallet_address).call()
        weth_amount = weth_balance / 10 ** 18

        # USDC残高
        usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
        usdc_balance = usdc_contract.functions.balanceOf(wallet_address).call()
        usdc_amount = usdc_balance / 10 ** 6

        return {
            'eth': eth_amount,
            'weth': weth_amount,
            'usdc': usdc_amount
        }

    except Exception as e:
        print(f"ウォレット残高取得エラー: {e}")
        return {'eth': 0, 'weth': 0, 'usdc': 0}


def get_current_nft_id():
    """現在のNFT IDを取得"""
    try:
        # 絶対パスで指定
        json_path = '/root/lpbot/tracked_nfts.json'

        with open(json_path, 'r') as f:
            data = json.load(f)
            nft_ids = data.get('nft_ids', [])
            current_nft = nft_ids[-1] if nft_ids else None
            return current_nft

    except Exception as e:
        print(f"NFT ID読み込みエラー: {e}")
        return None


if __name__ == '__main__':
    # まず投資履歴テーブルを作成
    conn = get_db_connection()
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS investment_history
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     timestamp
                     DATETIME
                     NOT
                     NULL,
                     action
                     TEXT
                     NOT
                     NULL,
                     amount_usd
                     REAL
                     NOT
                     NULL,
                     cumulative_investment
                     REAL,
                     note
                     TEXT,
                     created_at
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )
                 """)

    # fee_collection_historyテーブルも作成
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS fee_collection_history
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     timestamp
                     DATETIME
                     NOT
                     NULL,
                     nft_id
                     INTEGER,
                     tx_hash
                     TEXT,
                     amount0
                     REAL,
                     amount1
                     REAL,
                     amount0_usd
                     REAL,
                     amount1_usd
                     REAL,
                     total_usd
                     REAL,
                     gas_used
                     INTEGER,
                     gas_cost_eth
                     REAL,
                     gas_cost_usd
                     REAL,
                     net_profit_usd
                     REAL,
                     created_at
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )
                 """)

    conn.commit()
    conn.close()

    app.run(host='0.0.0.0', port=5000, debug=True)