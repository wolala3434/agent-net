import React, { useState, useEffect } from 'react';
import { getAdminRevenue } from '../../api/client';

const TIME_RANGES = [
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
  { value: 365, label: '近 1 年' },
];

function RevenueCard({ title, value, prefix }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-5">
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      <p className="text-2xl font-bold text-gray-900">
        {value != null ? `${prefix || '¥'}${typeof value === 'number' ? value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value}` : '-'}
      </p>
    </div>
  );
}

function TopAgentItem({ agent, rank }) {
  const earnings = agent.earnings || agent.total_earnings || 0;
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-3">
        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
          rank === 1 ? 'bg-yellow-100 text-yellow-700' :
          rank === 2 ? 'bg-gray-100 text-gray-600' :
          rank === 3 ? 'bg-orange-100 text-orange-600' :
          'bg-gray-50 text-gray-500'
        }`}>
          {rank}
        </span>
        <div>
          <p className="text-sm font-medium text-gray-800">{agent.name || agent.agent_name || '未知 Agent'}</p>
          {agent.provider && <p className="text-xs text-gray-400">{agent.provider}</p>}
        </div>
      </div>
      <span className="text-sm font-semibold text-gray-900">¥{earnings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
    </div>
  );
}

function TopAgentsBarChart({ topAgents }) {
  if (!topAgents || topAgents.length === 0) return null;
  const maxEarnings = Math.max(...topAgents.map((a) => a.earnings || a.total_earnings || 0), 1);

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Agent 收入排行</h3>
      <div className="space-y-3">
        {topAgents.map((agent, idx) => {
          const earnings = agent.earnings || agent.total_earnings || 0;
          const pct = (earnings / maxEarnings) * 100;
          return (
            <div key={agent.id || idx}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700 truncate max-w-[200px]">{agent.name || agent.agent_name || '未知 Agent'}</span>
                <span className="font-medium text-gray-900">¥{earnings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </div>
              <div className="w-full h-4 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    idx === 0 ? 'bg-yellow-400' :
                    idx === 1 ? 'bg-gray-400' :
                    idx === 2 ? 'bg-orange-400' :
                    'bg-blue-400'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Revenue() {
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    loadData();
  }, [days]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminRevenue(days);
      setRevenue(data);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="flex items-center gap-3 text-blue-600">
          <svg className="animate-spin h-6 w-6" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-red-500 text-lg mb-4">{error}</p>
        <button
          onClick={loadData}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  if (!revenue) {
    return (
      <div className="flex justify-center items-center py-20">
        <p className="text-gray-400 text-lg">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">收入概览</h1>
          <p className="mt-2 text-gray-500">查看平台收入数据和 Agent 收益排行</p>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          {TIME_RANGES.map((range) => (
            <button
              key={range.value}
              onClick={() => setDays(range.value)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                days === range.value
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Revenue Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <RevenueCard title="GMV（商品交易总额）" value={revenue.gmv} />
        <RevenueCard title="平台费用" value={revenue.platform_fees} />
        <RevenueCard title="Agent 总收益" value={revenue.agent_earnings_total} />
        <RevenueCard title="交易笔数" value={revenue.transaction_count} prefix="" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Agents Bar Chart */}
        {revenue.top_agents && revenue.top_agents.length > 0 && (
          <TopAgentsBarChart topAgents={revenue.top_agents} />
        )}

        {/* Top Agents List */}
        {revenue.top_agents && revenue.top_agents.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Agent 收益排名</h3>
            {revenue.top_agents.map((agent, idx) => (
              <TopAgentItem key={agent.id || idx} agent={agent} rank={idx + 1} />
            ))}
          </div>
        )}
      </div>

      {/* Empty fallback */}
      {(!revenue.top_agents || revenue.top_agents.length === 0) && (
        <div className="flex justify-center items-center py-12">
          <p className="text-gray-400">暂无数据</p>
        </div>
      )}
    </div>
  );
}
