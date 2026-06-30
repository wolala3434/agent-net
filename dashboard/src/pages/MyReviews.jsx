import React, { useState, useEffect } from 'react';
import { getReviews, getUserId, submitReview, getSessions } from '../api/client';

function StarInput({ value, onChange, disabled }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={disabled}
          onClick={() => onChange(star)}
          className={`w-6 h-6 transition-colors ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <svg
            className={`w-full h-full ${star <= value ? 'text-yellow-400' : 'text-gray-200'}`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        </button>
      ))}
    </div>
  );
}

function PendingReviewCard({ task, onSubmitted }) {
  const [rating, setRating] = useState(0);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (rating === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitReview(task.agent_id, task.id, rating, text);
      setRating(0);
      setText('');
      onSubmitted(task.id);
    } catch (err) {
      setError('提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 mb-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-gray-900">{task.description || `任务 ${task.id}`}</h3>
          <p className="text-sm text-gray-500 mt-1">
            Agent: {task.agent_name || task.agent_id || '未知'}
          </p>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      <div className="mb-3">
        <p className="text-sm text-gray-600 mb-2">评分</p>
        <StarInput value={rating} onChange={setRating} disabled={submitting} />
      </div>

      <div className="mb-3">
        <p className="text-sm text-gray-600 mb-2">评价内容（选填）</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="分享你的使用体验..."
          rows={3}
          disabled={submitting}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={rating === 0 || submitting}
        className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
          rating === 0 || submitting
            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        {submitting ? '提交中...' : '提交评价'}
      </button>
    </div>
  );
}

function HistoryReviewCard({ review }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-5 mb-4">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-medium text-gray-900">
            {review.agent_name || review.agent_id || '未知 Agent'}
          </h3>
          {review.task_description && (
            <p className="text-sm text-gray-500 mt-1">{review.task_description}</p>
          )}
        </div>
        <StarInput value={review.rating} onChange={() => {}} disabled />
      </div>
      {(review.review_text || review.text) && (
        <p className="text-sm text-gray-600 mt-2">{review.review_text || review.text}</p>
      )}
      {review.created_at && (
        <p className="text-xs text-gray-400 mt-2">{review.created_at}</p>
      )}
    </div>
  );
}

export default function MyReviews() {
  const [activeTab, setActiveTab] = useState('pending');
  const [reviews, setReviews] = useState(null);
  const [pendingTasks, setPendingTasks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const userId = getUserId();
      const [reviewsRes, sessionsRes] = await Promise.all([
        getReviews(userId).catch(() => []),
        getSessions(50).catch(() => []),
      ]);
      setReviews(Array.isArray(reviewsRes) ? reviewsRes : []);
      setPendingTasks(Array.isArray(sessionsRes) ? sessionsRes : sessionsRes?.sessions || []);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitted = (taskId) => {
    if (pendingTasks) {
      setPendingTasks((prev) => (prev ? prev.filter((t) => t.id !== taskId) : []));
    }
    loadData();
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

  const tabs = [
    { key: 'pending', label: '待评价' },
    { key: 'history', label: '历史评价' },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">我的评价</h1>
        <p className="mt-2 text-gray-500">管理你的 Agent 使用评价</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Pending Tab */}
      {activeTab === 'pending' && (
        <>
          {pendingTasks && pendingTasks.length > 0 ? (
            pendingTasks.map((task) => (
              <PendingReviewCard key={task.id} task={task} onSubmitted={handleSubmitted} />
            ))
          ) : (
            <div className="flex justify-center items-center py-20">
              <p className="text-gray-400 text-lg">暂无数据</p>
            </div>
          )}
        </>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <>
          {reviews && reviews.length > 0 ? (
            reviews.map((review, idx) => (
              <HistoryReviewCard key={review.id || idx} review={review} />
            ))
          ) : (
            <div className="flex justify-center items-center py-20">
              <p className="text-gray-400 text-lg">暂无数据</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
