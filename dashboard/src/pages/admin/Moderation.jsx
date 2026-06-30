import React, { useState, useEffect } from 'react';
import { getAdminFlaggedReviews, deleteAdminReview } from '../../api/client';

function ReviewCard({ review, onDelete, deleting }) {
  const renderStars = (rating) => {
    return [1, 2, 3, 4, 5].map((star) => (
      <svg
        key={star}
        className={`w-4 h-4 ${star <= rating ? 'text-yellow-400' : 'text-gray-200'}`}
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
    ));
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 mb-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="font-medium text-gray-900">
              {review.agent_name || review.agent_id || '未知 Agent'}
            </h3>
            {review.rating != null && (
              <div className="flex items-center gap-1">
                <div className="flex">{renderStars(review.rating)}</div>
                <span className="text-xs text-gray-400">({review.rating}/5)</span>
              </div>
            )}
          </div>

          {review.user_name && (
            <p className="text-sm text-gray-500 mb-2">
              评价者: {review.user_name}
            </p>
          )}

          {(review.review_text || review.text) && (
            <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 mb-2">
              {review.review_text || review.text}
            </p>
          )}

          {review.created_at && (
            <p className="text-xs text-gray-400">{review.created_at}</p>
          )}
        </div>

        <button
          onClick={() => onDelete(review.id)}
          disabled={deleting === review.id}
          className={`ml-4 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            deleting === review.id
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-red-50 text-red-600 hover:bg-red-100'
          }`}
        >
          {deleting === review.id ? '删除中...' : '删除'}
        </button>
      </div>
    </div>
  );
}

export default function Moderation() {
  const [reviews, setReviews] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminFlaggedReviews();
      setReviews(data.reviews || []);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('确定要删除这条评价吗？')) return;
    setDeleting(id);
    try {
      await deleteAdminReview(id);
      if (reviews) {
        setReviews((prev) => (prev ? prev.filter((r) => r.id !== id) : []));
      }
    } catch (err) {
      alert('删除失败，请重试');
    } finally {
      setDeleting(null);
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
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">评价审核</h1>
        <p className="mt-2 text-gray-500">管理被标记的低分评价</p>
      </div>

      {/* Stats */}
      {reviews && (
        <div className="bg-white rounded-xl shadow-sm p-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-red-400 rounded-full" />
            <span className="text-sm text-gray-600">
              共 {reviews.length} 条被标记的评价
            </span>
          </div>
        </div>
      )}

      {/* Reviews List */}
      {reviews && reviews.length > 0 ? (
        <div>
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              review={review}
              onDelete={handleDelete}
              deleting={deleting}
            />
          ))}
        </div>
      ) : (
        <div className="flex justify-center items-center py-20">
          <div className="text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-300 mb-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-gray-400 text-lg">暂无数据</p>
            <p className="text-gray-300 text-sm mt-1">暂时没有需要审核的评价</p>
          </div>
        </div>
      )}
    </div>
  );
}
