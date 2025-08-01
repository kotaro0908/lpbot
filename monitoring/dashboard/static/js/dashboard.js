let revenueChart = null;
let transactionChart = null;

function updateDashboard() {
   fetch('/api/dashboard_data')
       .then(response => response.json())
       .then(data => {
           // KPIカードの更新
           document.getElementById('total-value').textContent = `$${data.total_value.toFixed(2)}`;
           document.getElementById('total-fees').textContent = `$${Math.abs(data.total_fees).toFixed(2)}`;
           document.getElementById('roi').textContent = `${data.roi.toFixed(1)}%`;
           
           // その他のデータ更新
           updateCharts(data);
           updateTransactions(data.recent_transactions);
       });
}

function updateCharts(data) {
   if (data.revenue_chart_data && revenueChart) {
       revenueChart.setData(data.revenue_chart_data);
   }
}

function updateTransactions(transactions) {
   const tbody = document.getElementById('transaction-tbody');
   if (tbody && transactions) {
       tbody.innerHTML = transactions.map(tx => `
           <tr>
               <td>${new Date(tx.timestamp).toLocaleString('ja-JP')}</td>
               <td>${tx.type}</td>
               <td>$${tx.amount.toFixed(2)}</td>
               <td><span class="badge ${tx.status === 'success' ? 'bg-success' : 'bg-danger'}">${tx.status}</span></td>
           </tr>
       `).join('');
   }
}

// 初期化
document.addEventListener('DOMContentLoaded', function() {
   updateDashboard();
   setInterval(updateDashboard, 30000);
});