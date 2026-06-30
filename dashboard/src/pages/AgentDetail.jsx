import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getAgent, getUserId } from '../api/client';
import StatusBadge from '../components/StatusBadge';

const RATING_LABELS = ['', '非常差', '较差', '一般', '较好', '非常好'];

function RatingDistribution({ distribution }) {
  if (!distribution) return null;
  const maxCount = Math.max(...Object.values(distribution), 1);
  return (
    <div className="space-y-2">
      {[5, 4, 3, 2, 1].map((star) => {
        const count = distribution[star] || 0;
        const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
        return (
          <div key={star} className="flex items-center gap-3">
            <span className="text-sm text-gray-600 w-16">{star} 星</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-yellow-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-sm text-gray-500 w-8">{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function SchemaView({ schema, title }) {
  if (!schema) return null;
  return (
    <div className="mb-4">
      <h4 className="text-sm font-medium text-gray-700 mb-2">{title}</h4>
      <pre className="bg-gray-50 p-3 rounded-lg text-xs text-gray-600 overflow-x-auto">
        {JSON.stringify(schema, null, 2)}
      </pre>
    </div>
  );
}

export default function AgentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    loadAgent();
  }, [id]);

  const loadAgent = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAgent(decodeURIComponent(id));
      setAgent(data);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const togglePin = () => {
    setPinned((prev) => !prev);
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
          onClick={loadAgent}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex justify-center items-center py-20">
        <p className="text-gray-400 text-lg">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-6 transition-colors"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        返回
      </button>

      {/* Header Card */}
      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center">
              <span className="text-2xl font-bold text-blue-600">
                {(agent.name || 'A')[0]}
              </span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{agent.name}</h1>
              <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                <span>提供者: {agent.provider || '未知'}</span>
                <span>版本: {agent.version || '1.0.0'}</span>
                {agent.status && <StatusBadge status={agent.status} />}
              </div>
            </div>
          </div>
          <button
            onClick={togglePin}
            className={`px-4 py-2 rounded-lg border transition-colors ${
              pinned
                ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-500 hover:text-blue-600'
            }`}
          >
            {pinned ? '已置顶' : '置顶'}
          </button>
        </div>

        {agent.description && (
          <p className="mt-4 text-gray-600 leading-relaxed">{agent.description}</p>
        )}

        {/* Rating summary */}
        {agent.avg_rating != null && (
          <div className="mt-4 flex items-center gap-2">
            <div className="flex">
              {[1, 2, 3, 4, 5].map((star) => (
                <svg
                  key={star}
                  className={`w-5 h-5 ${star <= Math.round(agent.avg_rating) ? 'text-yellow-400' : 'text-gray-200'}`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
            <span className="text-lg font-semibold text-gray-800">{agent.avg_rating.toFixed(1)}</span>
            <span className="text-sm text-gray-400">({agent.review_count || 0} 条评价)</span>
          </div>
        )}
      </div>

      {/* Skills */}
      {agent.skills && agent.skills.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">能力与技能</h2>
          <div className="space-y-4">
            {agent.skills.map((skill, idx) => (
              <div key={idx} className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 bg-blue-500 rounded-full" />
                  <h3 className="font-medium text-gray-800">{skill.name}</h3>
                  {skill.type && (
                    <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full">{skill.type}</span>
                  )}
                </div>
                {skill.description && (
                  <p className="text-sm text-gray-500 ml-4 mb-3">{skill.description}</p>
                )}
                <SchemaView schema={skill.input_schema} title="输入 Schema" />
                <SchemaView schema={skill.output_schema} title="输出 Schema" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rating Distribution */}
      {agent.rating_distribution && (
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">评分分布</h2>
          <RatingDistribution distribution={agent.rating_distribution} />
        </div>
      )}

      {/* Reviews */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">近期评价</h2>
        {agent.reviews && agent.reviews.length > 0 ? (
          <div className="space-y-4">
            {agent.reviews.map((review, idx) => (
              <div key={idx} className="border-b border-gray-100 last:border-0 pb-4 last:pb-0">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">{review.user_name || '匿名用户'}</span>
                  <div className="flex items-center gap-2">
                    <div className="flex">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <svg
                          key={star}
                          className={`w-4 h-4 ${star <= review.rating ? 'text-yellow-400' : 'text-gray-200'}`}
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      ))}
                    </div>
                    <span className="text-xs text-gray-400">{review.created_at || ''}</span>
                  </div>
                </div>
                {(review.review_text || review.text) && (
                  <p className="text-sm text-gray-600">{review.review_text || review.text}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-center py-6">暂无评价</p>
        )}
      </div>
    </div>
  );
}
