import React, { useState, useEffect } from 'react';
import { getAdminOverview } from '../../api/client';

function MetricCard({ title, value, subtitle, color }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      <p className={`text-3xl font-bold ${color || 'text-gray-900'}`}>
        {value != null ? value : '-'}
      </p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}

function AgentStatusChart({ agents }) {
  if (!agents) return null;
  const total = agents.total || 0;
  const active = agents.active || 0;
  const inactive = total - active;
  const activePct = total > 0 ? (active / total) * 100 : 0;

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Agent 状态分布</h3>
      <div className="flex items-center gap-4 mb-4">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
            <circle cx="18" cy="18" r="15.9" fill="none" stroke="#e5e7eb" strokeWidth="3" />
            <circle
              cx="18" cy="18" r="15.9"
              fill="none" stroke="#2563eb"
              strokeWidth="3"
              strokeDasharray={`${activePct} ${100 - activePct}`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-sm font-bold text-gray-700">{active}</span>
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-600" />
            <span className="text-sm text-gray-600">活跃: {active}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-gray-200" />
            <span className="text-sm text-gray-600">非活跃: {inactive}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Overview() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminOverview();
      setOverview(data);
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

  if (!overview) {
    return (
      <div className="flex justify-center items-center py-20">
        <p className="text-gray-400 text-lg">暂无数据</p>
      </div>
    );
  }

  const { agents, tasks, sessions, revenue } = overview;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">系统概览</h1>
        <p className="mt-2 text-gray-500">管理后台 - 平台整体运行状况</p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Agent 总数"
          value={agents?.total}
          subtitle={`活跃: ${agents?.active || 0}`}
          color="text-blue-600"
        />
        <MetricCard
          title="任务总数"
          value={tasks?.total}
          color="text-purple-600"
        />
        <MetricCard
          title="会话总数"
          value={sessions?.total}
          color="text-emerald-600"
        />
        <MetricCard
          title="总收入"
          value={revenue ? `¥${(revenue.gmv || 0).toLocaleString()}` : '-'}
          subtitle={`平台费用: ¥${(revenue?.platform_fees || 0).toLocaleString()}`}
          color="text-amber-600"
        />
      </div>

      {/* Revenue Detail */}
      {revenue && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">收入详情</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-600">GMV（商品交易总额）</span>
                <span className="font-semibold text-gray-900">¥{(revenue.gmv || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-gray-600">平台费用</span>
                <span className="font-semibold text-gray-900">¥{(revenue.platform_fees || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-600">平台净利润</span>
                <span className="font-semibold text-blue-600">
                  ¥{((revenue.platform_fees || 0) - (revenue.gmv || 0) * 0).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <AgentStatusChart agents={agents} />
        </div>
      )}

      {!revenue && !agents && (
        <div className="flex justify-center items-center py-12">
          <p className="text-gray-400">暂无数据</p>
        </div>
      )}
    </div>
  );
}
