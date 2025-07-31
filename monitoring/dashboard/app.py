# monitoring/dashboard/app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import json
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append('/root/lpbot')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# データベースパス
DB_PATH = '/root/lpbot/monitoring/lpbot.db'


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


@app.route('/api/dashboard_data')
def api_dashboard_data():
    """ダッシュボード用データAPI"""
    conn = get_db_connection()

    # 現在の総資産価値（仮実装）
    total_value = calculate_total_value()

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

    conn.close()

    return jsonify({
        'total_value': total_value,
        'total_investment': total_investment,
        'total_fees': total_fees,
        'total_gas': total_gas,
        'net_profit': total_fees - total_gas,
        'roi': ((total_value - total_investment) / total_investment * 100) if total_investment > 0 else 0
    })


def calculate_total_value():
    """現在の総資産価値を計算（TODO: The Graph連携）"""
    # 仮の値
    return 12450.23


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
    conn.commit()
    conn.close()

    app.run(host='0.0.0.0', port=5000, debug=True)