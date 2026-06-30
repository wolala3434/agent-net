import { useNavigate } from 'react-router-dom';
import StatusBadge from './StatusBadge';

const DOMAIN_LABELS = {
  general: '通用',
  code: '代码',
  writing: '写作',
  analysis: '分析',
  creative: '创意',
  productivity: '效率',
  education: '教育',
  finance: '金融',
  medical: '医疗',
  legal: '法律',
  chat: '对话',
  image: '图像',
  audio: '音频',
  video: '视频',
  data: '数据',
  search: '搜索',
};

export default function AgentCard({ agent, onPinToggle, pinned }) {
  const navigate = useNavigate();

  const {
    agent_id,
    id,
    name = '未命名 Agent',
    provider,
    provider_name,
    rating,
    avg_rating,
    review_count = 0,
    price = 0,
    domains = [],
    trial_status,
    description = '',
  } = agent || {};

  const resolvedId = agent_id || id;
  const resolvedProvider = provider || provider_name || '未知';
  const resolvedRating = rating ?? avg_rating ?? 0;
  const isFree = price === 0 || price == null;

  const handleClick = () => {
    navigate(`/agents/${encodeURIComponent(resolvedId)}`);
  };

  return (
    <div
      onClick={handleClick}
      className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md hover:border-blue-200 transition-all cursor-pointer group relative"
    >
      {/* Pin button */}
      {onPinToggle && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPinToggle(resolvedId);
          }}
          className={`absolute top-4 right-4 p-1.5 rounded-lg transition-all ${
            pinned
              ? 'text-blue-500 bg-blue-50 opacity-100'
              : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-gray-400'
          }`}
          aria-label={pinned ? '取消固定' : '固定'}
        >
          <svg className="w-4 h-4" fill={pinned ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
          </svg>
        </button>
      )}

      {/* Header */}
      <div className="flex items-start gap-3 mb-3 pr-6">
        {/* Avatar placeholder */}
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-sm shrink-0 shadow-sm">
          {name.charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-semibold text-gray-900 truncate">{name}</h3>
            {trial_status && <StatusBadge status="trial" />}
          </div>
          <p className="text-sm text-gray-500 truncate mt-0.5">{resolvedProvider}</p>
        </div>
      </div>

      {/* Rating & Price */}
      <div className="flex items-center gap-4 mb-3 text-sm">
        <div className="flex items-center gap-1">
          <span className="text-yellow-500">★</span>
          <span className="font-medium text-gray-800">{Number(resolvedRating).toFixed(1)}</span>
          <span className="text-gray-400">({review_count})</span>
        </div>
        <span className={`font-medium ${isFree ? 'text-green-600' : 'text-gray-700'}`}>
          {isFree ? '免费' : `¥${price}`}
        </span>
      </div>

      {/* Domain badges */}
      {domains && domains.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {domains.map((d) => (
            <span
              key={d}
              className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700"
            >
              {DOMAIN_LABELS[d] || d}
            </span>
          ))}
        </div>
      )}

      {/* Description */}
      {description && (
        <p className="text-sm text-gray-600 leading-relaxed line-clamp-2">{description}</p>
      )}
    </div>
  );
}
