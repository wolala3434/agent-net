import React, { useState, useEffect } from 'react';
import { getSessions, getSessionMessages } from '../api/client';
import StatusBadge from '../components/StatusBadge';

const STATUS_MAP = {
  pending: '待处理',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

function CollaborationDialogue({ taskId }) {
  const [messages, setMessages] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (expanded && !messages) {
      loadMessages();
    }
  }, [expanded]);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const data = await getSessionMessages(taskId);
      setMessages(Array.isArray(data) ? data : []);
    } catch {
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 transition-colors"
      >
        <svg
          className={`w-4 h-4 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {expanded ? '收起对话' : '查看协作对话'}
      </button>

      {expanded && (
        <div className="mt-3">
          {loading ? (
            <div className="flex items-center gap-2 text-blue-600 text-sm py-4">
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>加载中...</span>
            </div>
          ) : messages && messages.length > 0 ? (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {messages.map((msg, idx) => (
                <div key={idx} className="bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-400">#{msg.turn_number || idx + 1}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      msg.role === 'agent' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {msg.role === 'agent' ? 'Agent' : '用户'}
                    </span>
                    {msg.message_type && (
                      <span className="text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded">
                        {msg.message_type}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap">
                    {typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)}
                  </p>
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

function TaskCard({ task }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl shadow-sm p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="font-semibold text-gray-900">{task.description || `任务 ${task.id}`}</h3>
            <StatusBadge status={task.status} labels={STATUS_MAP} />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
            {task.agent_name && <span>Agent: {task.agent_name}</span>}
            {task.agent_id && !task.agent_name && <span>Agent ID: {task.agent_id}</span>}
            {task.created_at && <span>创建时间: {task.created_at}</span>}
            {task.completed_at && <span>完成时间: {task.completed_at}</span>}
          </div>
        </div>
        <button
          onClick={() => setExpanded((prev) => !prev)}
          className="ml-4 p-1 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {task.result && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-400 mb-1">执行结果</p>
          <p className="text-sm text-gray-700">{task.result}</p>
        </div>
      )}

      {expanded && <CollaborationDialogue taskId={task.id} />}
    </div>
  );
}

export default function TaskTracker() {
  const [tasks, setTasks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSessions(50);
      setTasks(Array.isArray(data) ? data : data?.sessions || []);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const filteredTasks = tasks
    ? filter === 'all'
      ? tasks
      : tasks.filter((t) => t.status === filter)
    : [];

  const filterOptions = [
    { value: 'all', label: '全部' },
    { value: 'running', label: '进行中' },
    { value: 'completed', label: '已完成' },
    { value: 'pending', label: '待处理' },
    { value: 'failed', label: '失败' },
  ];

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
          onClick={loadTasks}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">任务跟踪</h1>
        <p className="mt-2 text-gray-500">查看和管理所有任务执行情况</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-6">
        {filterOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === opt.value
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 border border-gray-300 hover:border-blue-500 hover:text-blue-600'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Task count */}
      {tasks && (
        <p className="text-sm text-gray-500 mb-4">
          共 {filteredTasks.length} 个任务
        </p>
      )}

      {/* Task list */}
      {filteredTasks.length > 0 ? (
        <div className="space-y-4">
          {filteredTasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      ) : (
        <div className="flex justify-center items-center py-20">
          <p className="text-gray-400 text-lg">暂无数据</p>
        </div>
      )}
    </div>
  );
}
