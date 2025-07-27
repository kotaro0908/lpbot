#!/usr/bin/env python3
import os
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# 設定
RPC_URL = os.getenv("RPC_URL")
POSITION_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"


def test_rpc_limits():
    print("=== 🔍 QuickNode RPC制限テスト ===")
    print(f"📍 RPC URL: {RPC_URL[:50]}...")

    # Web3接続
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Web3接続失敗")
        return

    current_block = w3.eth.block_number
    print(f"📊 現在ブロック: {current_block}")

    # Transfer イベントシグネチャ
    transfer_signature = w3.keccak(text="Transfer(address,address,uint256)")

    # 段階的に制限をテスト
    test_ranges = [
        (1000, "1,000ブロック"),
        (2000, "2,000ブロック"),
        (5000, "5,000ブロック"),
        (10000, "10,000ブロック"),
        (15000, "15,000ブロック"),
        (20000, "20,000ブロック"),
        (30000, "30,000ブロック"),
        (50000, "50,000ブロック")
    ]

    successful_ranges = []
    failed_ranges = []

    for block_range, description in test_ranges:
        from_block = current_block - block_range
        to_block = current_block

        print(f"\n🔍 {description} テスト中...")
        print(f"   範囲: {from_block} ～ {to_block}")

        try:
            start_time = time.time()

            # 基本的なTransferイベント検索
            filter_params = {
                'address': POSITION_MANAGER_ADDRESS,
                'topics': [transfer_signature.hex()],
                'fromBlock': from_block,
                'toBlock': to_block
            }

            logs = w3.eth.get_logs(filter_params)
            end_time = time.time()

            duration = end_time - start_time
            print(f"   ✅ 成功: {len(logs)}個のイベント ({duration:.2f}秒)")
            successful_ranges.append((block_range, len(logs), duration))

        except Exception as e:
            print(f"   ❌ 失敗: {e}")
            failed_ranges.append((block_range, str(e)))

            # 413エラーの場合は詳細表示
            if "413" in str(e):
                print("   🚨 413 Request Entity Too Large - RPC制限")
            elif "429" in str(e):
                print("   🚨 429 Too Many Requests - レート制限")

        # 少し待機（レート制限回避）
        time.sleep(0.5)

    # 結果サマリー
    print(f"\n📊 テスト結果サマリー:")
    print(f"✅ 成功した範囲:")
    for block_range, event_count, duration in successful_ranges:
        print(f"   {block_range:,}ブロック: {event_count}イベント ({duration:.2f}秒)")

    print(f"\n❌ 失敗した範囲:")
    for block_range, error in failed_ranges:
        print(f"   {block_range:,}ブロック: {error}")

    # プラン推定
    if successful_ranges:
        max_successful = max(successful_ranges, key=lambda x: x[0])
        max_range = max_successful[0]

        print(f"\n💡 制限分析:")
        print(f"   最大成功範囲: {max_range:,}ブロック")

        if max_range >= 50000:
            print("   🎯 推定プラン: Pro/Scale (高制限)")
        elif max_range >= 20000:
            print("   🎯 推定プラン: Build+ (中制限)")
        elif max_range >= 10000:
            print("   🎯 推定プラン: Build/Basic (標準制限)")
        else:
            print("   🎯 推定プラン: Discover/無料 (低制限)")

    # 推奨事項
    print(f"\n🔧 推奨事項:")
    if not successful_ranges or max(r[0] for r in successful_ranges) < 15000:
        print("   1. QuickNodeダッシュボードでプラン確認")
        print("   2. Archive Data Accessが有効か確認")
        print("   3. eth_getLogsの制限値確認")
        print("   4. 可能であればプランアップグレード検討")
    else:
        print("   ✅ 現在の制限で十分な範囲をカバー")


if __name__ == "__main__":
    test_rpc_limits()