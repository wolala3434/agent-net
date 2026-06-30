import React, { useState, useEffect } from 'react';
import { getAgents, getSessions, getSessionMessages } from '../api/client';

function StatCard({ label, value, color }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-5">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color || 'text-gray-900'}`}>{value ?? '-'}</p>
    </div>
  );
}

function SessionItem({ session }) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState(null);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const toggleExpand = async () => {
    if (!expanded && !messages) {
      setLoadingMessages(true);
      try {
        const data = await getSessionMessages(session.id);
        setMessages(Array.isArray(data) ? data : []);
      } catch {
        setMessages([]);
      } finally {
        setLoadingMessages(false);
      }
    }
    setExpanded((prev) => !prev);
  };

  return (
    <div className="border border-gray-100 rounded-lg">
      <button
        onClick={toggleExpand}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${session.status === 'active' ? 'bg-green-400' : 'bg-gray-300'}`} />
          <div>
            <p className="font-medium text-gray-800 text-sm">
              {session.agent_name || session.agent_id || '未知 Agent'}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {session.created_at || ''} {session.user_name ? `- ${session.user_name}` : ''}
            </p>
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="border-t border-gray-100 p-4 bg-gray-50">
          {loadingMessages ? (
            <div className="flex items-center gap-2 text-blue-600 text-sm">
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>加载中...</span>
            </div>
          ) : messages && messages.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {messages.map((msg, idx) => (
                <div key={idx} className="bg-white rounded p-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      msg.role === 'agent' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {msg.role === 'agent' ? 'Agent' : '用户'}
                    </span>
                    <span className="text-xs text-gray-400">{msg.created_at || ''}</span>
                  </div>
                  <p className="text-gray-600">{msg.content || JSON.stringify(msg)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm text-center py-4">暂无数据</p>
          )}
        </div>
      )}
    </div>
  );
}

function TaskItem({ task }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-3">
        <span className={`w-2 h-2 rounded-full ${
          task.status === 'completed' ? 'bg-green-400' :
          task.status === 'running' ? 'bg-blue-400' : 'bg-gray-300'
        }`} />
        <div>
          <p className="text-sm font-medium text-gray-700">{task.description || task.id}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {task.agent_name || task.agent_id || '未知 Agent'}
          </p>
        </div>
      </div>
      <span className={`text-xs px-2 py-1 rounded-full ${
        task.status === 'completed' ? 'bg-green-50 text-green-600' :
        task.status === 'running' ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'
      }`}>
        {task.status === 'completed' ? '已完成' : task.status === 'running' ? '进行中' : task.status || '未知'}
      </span>
    </div>
  );
}

export default function NetworkFeed() {
  const [sessions, setSessions] = useState(null);
  const [agents, setAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionsRes, agentsRes] = await Promise.all([
        getSessions(20).catch(() => []),
        getAgents({}).catch(() => ({ agents: [] })),
      ]);
      setSessions(Array.isArray(sessionsRes) ? sessionsRes : sessionsRes?.sessions || []);
      setAgents(agentsRes.agents || []);
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

  const activeSessions = sessions ? sessions.filter((s) => s.status === 'active') : [];
  const completedTasks = sessions ? sessions.filter((s) => s.status === 'completed') : [];
  const onlineAgents = agents ? agents.filter((a) => a.status === 'active' || a.status === 'online') : [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">网络动态</h1>
        <p className="mt-2 text-gray-500">实时了解平台运行状态</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="在线 Agent" value={onlineAgents.length} color="text-green-600" />
        <StatCard label="活跃会话" value={activeSessions.length} color="text-blue-600" />
        <StatCard label="已完成任务" value={completedTasks.length} color="text-emerald-600" />
        <StatCard label="总 Agent 数" value={agents ? agents.length : '-'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Sessions */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">活跃会话</h2>
          {activeSessions.length > 0 ? (
            <div className="space-y-3">
              {activeSessions.map((session) => (
                <SessionItem key={session.id} session={session} />
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-center py-8">暂无数据</p>
          )}
        </div>

        {/* Recent Tasks */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">最近任务</h2>
          {sessions && sessions.length > 0 ? (
            <div>
              {sessions.slice(0, 10).map((session) => (
                <TaskItem key={session.id} task={session} />
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-center py-8">暂无数据</p>
          )}
        </div>
      </div>
    </div>
  );
}
