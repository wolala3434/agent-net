const statusConfig = {
  trial: {
    label: '试用中',
    className: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  },
  verified: {
    label: '已验证',
    className: 'bg-green-100 text-green-800 border border-green-200',
  },
  low_quality: {
    label: '低质量',
    className: 'bg-red-100 text-red-800 border border-red-200',
  },
};

const dotConfig = {
  active: {
    dotClass: 'bg-green-500',
    label: '活跃',
  },
  inactive: {
    dotClass: 'bg-gray-400',
    label: '离线',
  },
  online: {
    dotClass: 'bg-green-500',
    label: '在线',
  },
  offline: {
    dotClass: 'bg-gray-400',
    label: '离线',
  },
};

const dynamicStatusColors = {
  running: 'bg-blue-100 text-blue-700 border border-blue-200',
  completed: 'bg-green-100 text-green-700 border border-green-200',
  pending: 'bg-yellow-100 text-yellow-700 border border-yellow-200',
  failed: 'bg-red-100 text-red-700 border border-red-200',
  cancelled: 'bg-gray-100 text-gray-600 border border-gray-200',
};

// Generic fallback for unknown statuses
const defaultColors = 'bg-gray-100 text-gray-600 border border-gray-200';

export default function StatusBadge({ status, size = 'sm', dot = false, labels }) {
  // Dot-style badge (e.g. active/inactive)
  if (dot) {
    const config = dotConfig[status];
    if (!config) return null;
    return (
      <span className="inline-flex items-center gap-1.5">
        <span className={`inline-block w-2 h-2 rounded-full ${config.dotClass}`} />
        <span className={`text-gray-600 ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>
          {config.label}
        </span>
      </span>
    );
  }

  // Check built-in status config first
  const builtIn = statusConfig[status];
  if (builtIn) {
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${builtIn.className}`}>
        {builtIn.label}
      </span>
    );
  }

  // Support custom labels map (e.g., from TaskTracker)
  if (labels && labels[status]) {
    const colorClass = dynamicStatusColors[status] || defaultColors;
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${colorClass}`}>
        {labels[status]}
      </span>
    );
  }

  // Dynamic known statuses (running, completed, etc.)
  if (dynamicStatusColors[status]) {
    const labelMap = {
      running: '进行中',
      completed: '已完成',
      pending: '待处理',
      failed: '失败',
      cancelled: '已取消',
    };
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${dynamicStatusColors[status]}`}>
        {labelMap[status]}
      </span>
    );
  }

  // Fallback: render unknown status as a plain label
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${defaultColors}`}>
      {status || '未知'}
    </span>
  );
}
