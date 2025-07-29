#!/usr/bin/env python3
"""
JSON Logger for LP BOT
JSONログ出力用の共通モジュール
"""

import json
import datetime
import os
import glob
import shutil
from typing import Dict, Any, Optional
from datetime import datetime as dt, timedelta


class JSONLogger:
    """LP BOT用JSONログ出力クラス"""

    @staticmethod
    def log_to_json(log_type: str, log_data: Dict[str, Any]) -> None:
        """JSONログファイルへの出力"""
        try:
            # タイムスタンプとタイプを追加
            log_data['timestamp'] = dt.now().isoformat()
            log_data['type'] = log_type

            # 日付別ファイル名
            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"logs_{today}.json"

            # JSONLファイル形式で追記
            with open(filename, 'a', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write('\n')

        except Exception as e:
            # JSON出力エラーがBOT本体を止めないように
            print(f"[WARNING] JSON log error: {e}")

    @staticmethod
    def log_rebalance(reason: str, old_nft_id: Optional[int], new_nft_id: Optional[int],
                      old_tick_lower: Optional[int] = None, old_tick_upper: Optional[int] = None,
                      new_tick_lower: Optional[int] = None, new_tick_upper: Optional[int] = None,
                      price_at_rebalance: Optional[float] = None, estimated_amount: Optional[float] = None,
                      swap_executed: bool = False, retry_count: int = 0,
                      tx_hash: Optional[str] = None, error_message: Optional[str] = None,
                      success: bool = True) -> None:
        """リバランスログ専用メソッド"""
        log_data = {
            "reason": reason,
            "old_nft_id": old_nft_id,
            "new_nft_id": new_nft_id,
            "old_tick_lower": old_tick_lower,
            "old_tick_upper": old_tick_upper,
            "new_tick_lower": new_tick_lower,
            "new_tick_upper": new_tick_upper,
            "price_at_rebalance": price_at_rebalance,
            "estimated_amount": estimated_amount,
            "swap_executed": swap_executed,
            "retry_count": retry_count,
            "tx_hash": tx_hash,
            "error_message": error_message,
            "success": success
        }
        JSONLogger.log_to_json("rebalance", log_data)

    @staticmethod
    def log_system(log_level: str, function_name: str, message: str,
                   execution_time_ms: Optional[int] = None,
                   error_details: Optional[str] = None) -> None:
        """システムログ専用メソッド"""
        log_data = {
            "log_level": log_level,
            "function_name": function_name,
            "message": message,
            "execution_time_ms": execution_time_ms,
            "error_details": error_details
        }
        JSONLogger.log_to_json("system", log_data)

    @staticmethod
    def log_swap(from_token: str, to_token: str, amount: float,
                 swap_direction: str, success: bool = True,
                 tx_hash: Optional[str] = None, error_message: Optional[str] = None) -> None:
        """SWAP実行ログ専用メソッド"""
        log_data = {
            "from_token": from_token,
            "to_token": to_token,
            "amount": amount,
            "swap_direction": swap_direction,
            "success": success,
            "tx_hash": tx_hash,
            "error_message": error_message
        }
        JSONLogger.log_to_json("swap", log_data)

    @staticmethod
    def log_fund_change(change_type: str, amount_usd: float,
                        trigger_action: Optional[str] = None) -> None:
        """資金変更検知ログ"""
        log_data = {
            "change_type": change_type,  # "deposit", "withdrawal"
            "amount_usd": amount_usd,
            "trigger_action": trigger_action  # "rebalance", "none"
        }
        JSONLogger.log_to_json("fund_change", log_data)

    @staticmethod
    def log_gas_retry(function_name: str, attempt: int, gas_limit: int,
                      gas_multiplier: float, success: bool = False) -> None:
        """ガスリトライログ"""
        log_data = {
            "function_name": function_name,
            "attempt": attempt,
            "gas_limit": gas_limit,
            "gas_multiplier": gas_multiplier,
            "success": success
        }
        JSONLogger.log_to_json("gas_retry", log_data)

    @staticmethod
    def cleanup_old_logs(days_to_keep: int = 7) -> None:
        """古いログファイルをアーカイブ（デフォルト7日以上前）"""
        try:
            cutoff_date = dt.now() - timedelta(days=days_to_keep)
            archived_count = 0

            for log_file in glob.glob("logs_*.json"):
                # ファイル名から日付を抽出
                try:
                    date_str = log_file.replace("logs_", "").replace(".json", "")
                    file_date = dt.strptime(date_str, "%Y-%m-%d")

                    if file_date < cutoff_date:
                        # archiveフォルダに移動
                        os.makedirs("archive", exist_ok=True)
                        shutil.move(log_file, f"archive/{log_file}")
                        print(f"[INFO] Archived: {log_file}")
                        archived_count += 1
                except ValueError:
                    # 日付形式が不正なファイルはスキップ
                    print(f"[WARNING] Invalid log file name: {log_file}")
                    continue

            if archived_count > 0:
                print(f"[INFO] Total {archived_count} files archived")

        except Exception as e:
            print(f"[WARNING] Log cleanup error: {e}")

    @staticmethod
    def validate_json_file(filename: Optional[str] = None) -> tuple:
        """JSONLファイルの整合性チェック"""
        if filename is None:
            filename = f"logs_{datetime.date.today().strftime('%Y-%m-%d')}.json"

        valid_lines = 0
        invalid_lines = 0

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if not line.strip():  # 空行はスキップ
                        continue
                    try:
                        json.loads(line.strip())
                        valid_lines += 1
                    except json.JSONDecodeError as e:
                        invalid_lines += 1
                        print(f"[ERROR] Invalid JSON at line {i + 1}: {e}")

            print(f"[INFO] Validation result for {filename}")
            print(f"  ✅ Valid lines: {valid_lines}")
            print(f"  ❌ Invalid lines: {invalid_lines}")
            return valid_lines, invalid_lines

        except FileNotFoundError:
            print(f"[ERROR] File not found: {filename}")
            return 0, 0
        except Exception as e:
            print(f"[ERROR] Validation error: {e}")
            return 0, 0

    @staticmethod
    def get_log_stats(filename: Optional[str] = None) -> Dict[str, Any]:
        """ログ統計情報の取得"""
        if filename is None:
            filename = f"logs_{datetime.date.today().strftime('%Y-%m-%d')}.json"

        stats = {
            "filename": filename,
            "total_lines": 0,
            "log_types": {},
            "error_count": 0,
            "file_size_kb": 0
        }

        try:
            # ファイルサイズ
            if os.path.exists(filename):
                stats["file_size_kb"] = os.path.getsize(filename) / 1024

            # ログ内容の統計
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        log_entry = json.loads(line.strip())
                        stats["total_lines"] += 1

                        # タイプ別カウント
                        log_type = log_entry.get("type", "unknown")
                        stats["log_types"][log_type] = stats["log_types"].get(log_type, 0) + 1

                        # エラーカウント
                        if log_entry.get("log_level") == "ERROR" or not log_entry.get("success", True):
                            stats["error_count"] += 1

                    except:
                        continue

            return stats

        except FileNotFoundError:
            return stats
        except Exception as e:
            print(f"[ERROR] Stats generation error: {e}")
            return stats


# 使いやすいようにインスタンスメソッドも提供
json_logger = JSONLogger()

# 使用例とテスト
if __name__ == "__main__":
    print("=== JSON Logger テスト ===")

    # 1. リバランスログのテスト
    JSONLogger.log_rebalance(
        reason="range_out",
        old_nft_id=4717342,
        new_nft_id=4717400,
        old_tick_lower=-193700,
        old_tick_upper=-193600,
        new_tick_lower=-193750,
        new_tick_upper=-193650,
        price_at_rebalance=3900.5,
        estimated_amount=95.0,
        swap_executed=True,
        success=True,
        tx_hash="0xabc123def456..."
    )
    print("✅ リバランスログ出力")

    # 2. システムログのテスト
    JSONLogger.log_system(
        log_level="ERROR",
        function_name="add_liquidity",
        message="Gas estimation failed, retrying with higher gas",
        execution_time_ms=1500,
        error_details="Insufficient funds for gas"
    )
    print("✅ システムログ出力")

    # 3. SWAPログのテスト
    JSONLogger.log_swap(
        from_token="USDC",
        to_token="WETH",
        amount=100.0,
        swap_direction="USDC_TO_ETH",
        success=True,
        tx_hash="0xdef789..."
    )
    print("✅ SWAPログ出力")

    # 4. 資金変更ログのテスト
    JSONLogger.log_fund_change(
        change_type="deposit",
        amount_usd=50.0,
        trigger_action="rebalance"
    )
    print("✅ 資金変更ログ出力")

    # 5. ガスリトライログのテスト
    JSONLogger.log_gas_retry(
        function_name="mint",
        attempt=2,
        gas_limit=882472,
        gas_multiplier=1.5,
        success=True
    )
    print("✅ ガスリトライログ出力")

    # 6. ファイル検証
    print("\n=== ファイル検証 ===")
    JSONLogger.validate_json_file()

    # 7. 統計情報
    print("\n=== ログ統計 ===")
    stats = JSONLogger.get_log_stats()
    print(f"Total lines: {stats['total_lines']}")
    print(f"Log types: {stats['log_types']}")
    print(f"Error count: {stats['error_count']}")
    print(f"File size: {stats['file_size_kb']:.2f} KB")

    print(f"\n📁 ログファイル: logs_{datetime.date.today().strftime('%Y-%m-%d')}.json")
    print("✅ 全テスト完了")