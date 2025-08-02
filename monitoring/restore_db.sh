#!/bin/bash
# データベース復元スクリプト

echo "🔄 LP BOT データベースを復元中..."

# monitoring ディレクトリに移動
cd "$(dirname "$0")"

# 既存DBのバックアップ
if [ -f "lpbot.db" ]; then
    cp "lpbot.db" "lpbot.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ 既存DBをバックアップしました"
fi

# 新規DB作成
rm -f "lpbot.db"
sqlite3 "lpbot.db" < db_schema_and_config.sql

echo "✅ データベーススキーマと設定データを復元しました"
echo ""
echo "📊 復元されたテーブル:"
sqlite3 "lpbot.db" ".tables"

echo ""
echo "🔄 次のステップ（データ収集）:"
echo "   cd collectors"  
echo "   python json_importer.py --all"
echo "   python external_collector.py"
