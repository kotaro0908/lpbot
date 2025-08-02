#!/bin/bash
# スキーマ更新スクリプト（テーブル構造変更時に実行）

echo "🔄 データベーススキーマを更新中..."

cd "$(dirname "$0")"

sqlite3 lpbot.db << 'SQLEOF' > db_schema_and_config.sql
.schema
.mode insert metadata
SELECT * FROM metadata;

.mode insert daily_performance  
SELECT * FROM daily_performance;
.mode insert rebalance_history
SELECT * FROM rebalance_history 
WHERE reason = 'range_out' AND success = 1 
ORDER BY timestamp DESC 
LIMIT 5;

.mode insert fee_collection_history
SELECT * FROM fee_collection_history 
ORDER BY timestamp DESC 
LIMIT 5;
SQLEOF
FILE_SIZE=$(ls -lh db_schema_and_config.sql | awk '{print $5}')
echo "✅ スキーマファイルを更新しました（サイズ: $FILE_SIZE）"

echo ""
echo "🎯 次のステップ:"
echo "   git add monitoring/db_schema_and_config.sql"
echo "   git commit -m 'スキーマ更新'"
echo "   git push"
