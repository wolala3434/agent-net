import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getBillingAccount } from '../api/client';

const navLinks = [
  { to: '/', label: '探索广场', icon: '🔍' },
  { to: '/network', label: '动态网络', icon: '🌐' },
  { to: '/tasks', label: '任务追踪', icon: '📋' },
  { to: '/reviews', label: '我的评价', icon: '⭐' },
  { to: '/sdk', label: '开发指南', icon: '🔧' },
];

const adminLinks = [
  { to: '/admin', label: '管理概览', icon: '📊' },
  { to: '/admin/approval', label: 'Agent 审核', icon: '✅' },
  { to: '/admin/revenue', label: '收入统计', icon: '💰' },
  { to: '/admin/moderation', label: '内容审核', icon: '🛡️' },
];

export default function Layout({ user, balance, onBalanceChange, onLogout }) {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isAdmin = user?.id === 'admin';

  useEffect(() => {
    if (user?.id) {
      getBillingAccount().then((data) => {
        if (data?.balance !== undefined) {
          onBalanceChange(data.balance);
        }
      });
    }
  }, [user?.id, onBalanceChange]);

  const handleLogout = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-30 w-64 bg-white border-r border-gray-200
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span className="text-lg font-bold text-blue-600">Agent Internet</span>
          </div>
        </div>

        {/* User info */}
        <div className="px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-semibold text-sm shadow-sm">
              {user?.id?.charAt(0)?.toUpperCase() || '?'}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{user?.id || '未登录'}</p>
              {balance !== null && (
                <p className="text-xs text-gray-500 mt-0.5">余额: ¥{Number(balance).toFixed(2)}</p>
              )}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <span className="text-lg leading-none">{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}

          {/* Admin section */}
          {isAdmin && (
            <div className="pt-5 mt-4 border-t border-gray-100">
              <p className="px-3 pb-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                管理后台
              </p>
              {adminLinks.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/admin'}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`
                  }
                >
                  <span className="text-lg leading-none">{link.icon}</span>
                  <span>{link.label}</span>
                </NavLink>
              ))}
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 shrink-0">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-600 transition-colors w-full py-1"
          >
            <span className="text-lg leading-none">🚪</span>
            <span>退出登录</span>
          </button>
          <p className="mt-2 text-xs text-gray-400">Agent Internet v1.0.0</p>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar (mobile only) */}
        <header className="lg:hidden h-14 flex items-center px-4 bg-white border-b border-gray-200 shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 -ml-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="打开菜单"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="ml-2 text-base font-semibold text-gray-900">Agent Internet</span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
