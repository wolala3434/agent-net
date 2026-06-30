const statusConfig = {
  trial: {
    label: 'Trial',
    className: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  },
  verified: {
    label: 'Verified',
    className: 'bg-green-100 text-green-800 border border-green-200',
  },
  low_quality: {
    label: 'Needs review',
    className: 'bg-red-100 text-red-800 border border-red-200',
  },
};

const dotConfig = {
  active: {
    dotClass: 'bg-green-500',
    label: 'Active',
  },
  inactive: {
    dotClass: 'bg-gray-400',
    label: 'Inactive',
  },
  online: {
    dotClass: 'bg-green-500',
    label: 'Online',
  },
  offline: {
    dotClass: 'bg-gray-400',
    label: 'Offline',
  },
};

const dynamicStatusColors = {
  running: 'bg-blue-100 text-blue-700 border border-blue-200',
  completed: 'bg-green-100 text-green-700 border border-green-200',
  pending: 'bg-yellow-100 text-yellow-700 border border-yellow-200',
  failed: 'bg-red-100 text-red-700 border border-red-200',
  cancelled: 'bg-gray-100 text-gray-600 border border-gray-200',
};

const defaultColors = 'bg-gray-100 text-gray-600 border border-gray-200';

export default function StatusBadge({ status, size = 'sm', dot = false, labels }) {
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

  const builtIn = statusConfig[status];
  if (builtIn) {
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${builtIn.className}`}>
        {builtIn.label}
      </span>
    );
  }

  if (labels && labels[status]) {
    const colorClass = dynamicStatusColors[status] || defaultColors;
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${colorClass}`}>
        {labels[status]}
      </span>
    );
  }

  if (dynamicStatusColors[status]) {
    const labelMap = {
      running: 'Running',
      completed: 'Completed',
      pending: 'Pending',
      failed: 'Failed',
      cancelled: 'Cancelled',
    };
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
    return (
      <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${dynamicStatusColors[status]}`}>
        {labelMap[status]}
      </span>
    );
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClasses} ${defaultColors}`}>
      {status || 'Unknown'}
    </span>
  );
}
