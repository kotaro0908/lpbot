#!/bin/bash

# 既存のcronジョブを確認
echo "📋 現在のcronジョブ:"
crontab -l

# 新しいcronジョブを追加
echo "🔧 external_collector.py用のcronジョブを追加中..."

# 現在のcrontabを取得し、新しいジョブを追加
(crontab -l 2>/dev/null; echo "30 */1 * * * cd /root/lpbot && /root/lpbot/venv/bin/python /root/lpbot/monitoring/collectors/external_collector.py >> /root/lpbot/monitoring/collectors/external_collector.log 2>&1") | crontab -

echo "✅ cronジョブ追加完了"
echo ""
echo "📋 更新後のcronジョブ:"
crontab -l