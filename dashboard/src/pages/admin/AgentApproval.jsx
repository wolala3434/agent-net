import React, { useState, useEffect } from 'react';
import { getAdminPendingAgents, approveAgent, rejectAgent, getAllAdminAgents } from '../../api/client';
import StatusBadge from '../../components/StatusBadge';

function AgentRow({ agent, onApprove, onReject, showActions }) {
  return (
    <div className="flex items-center justify-between py-4 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
          <span className="text-sm font-bold text-blue-600">{(agent.name || 'A')[0]}</span>
        </div>
        <div>
          <p className="font-medium text-gray-900">{agent.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-gray-500">{agent.provider || '未知提供者'}</span>
            <span className="text-xs text-gray-300">|</span>
            <span className="text-xs text-gray-500">v{agent.version || '1.0.0'}</span>
            {agent.domain && (
              <>
                <span className="text-xs text-gray-300">|</span>
                <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{agent.domain}</span>
              </>
            )}
          </div>
          {agent.description && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-1">{agent.description}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {agent.status && <StatusBadge status={agent.status} />}
        {showActions && (
          <div className="flex items-center gap-2 ml-3">
            <button
              onClick={() => onApprove(agent.id)}
              className="px-3 py-1.5 bg-green-500 text-white text-xs rounded-lg hover:bg-green-600 transition-colors"
            >
              通过
            </button>
            <button
              onClick={() => onReject(agent.id)}
              className="px-3 py-1.5 bg-red-500 text-white text-xs rounded-lg hover:bg-red-600 transition-colors"
            >
              拒绝
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentApproval() {
  const [pendingAgents, setPendingAgents] = useState(null);
  const [allAgents, setAllAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pendingRes, allRes] = await Promise.all([
        getAdminPendingAgents().catch(() => ({ agents: [] })),
        getAllAdminAgents().catch(() => ({ agents: [] })),
      ]);
      setPendingAgents(pendingRes.agents || []);
      setAllAgents(allRes.agents || []);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id) => {
    setActionLoading(id);
    try {
      await approveAgent(id);
      await loadData();
    } catch (err) {
      alert('操作失败，请重试');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id) => {
    setActionLoading(id);
    try {
      await rejectAgent(id);
      await loadData();
    } catch (err) {
      alert('操作失败，请重试');
    } finally {
      setActionLoading(null);
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

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Agent 审核</h1>
        <p className="mt-2 text-gray-500">审核新提交的 Agent 并管理已有 Agent</p>
      </div>

      {/* Pending Agents */}
      <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">待审核 Agent</h2>
          {pendingAgents && (
            <span className="text-sm px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full">
              {pendingAgents.length} 个待审核
            </span>
          )}
        </div>
        {pendingAgents && pendingAgents.length > 0 ? (
          <div>
            {pendingAgents.map((agent) => (
              <AgentRow
                key={agent.id}
                agent={agent}
                onApprove={handleApprove}
                onReject={handleReject}
                showActions
              />
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-center py-8">暂无数据</p>
        )}
      </div>

      {/* All Agents */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">全部 Agent</h2>
          {allAgents && (
            <span className="text-sm text-gray-500">共 {allAgents.length} 个</span>
          )}
        </div>
        {allAgents && allAgents.length > 0 ? (
          <div>
            {allAgents.map((agent) => (
              <AgentRow key={agent.id} agent={agent} showActions={false} />
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-center py-8">暂无数据</p>
        )}
      </div>
    </div>
  );
}
