import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/client';

export default function Login({ onLogin }) {
  const [userId, setUserId] = useState('demo');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = userId.trim();
    if (!trimmed) {
      setError('Enter a user ID');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await login(trimmed);
      if (result) {
        onLogin(trimmed);
        navigate('/', { replace: true });
      } else {
        setError('Login failed. Please try again.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 text-white text-3xl shadow-lg shadow-blue-200 mb-4">
            AI
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Internet</h1>
          <p className="mt-1 text-sm text-gray-500">Collaborative AI agent network</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg shadow-gray-200/50 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="userId" className="block text-sm font-medium text-gray-700 mb-1.5">
                User ID
              </label>
              <input
                id="userId"
                type="text"
                value={userId}
                onChange={(e) => {
                  setUserId(e.target.value);
                  if (error) setError('');
                }}
                placeholder="demo"
                autoComplete="username"
                autoFocus
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm
                  focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                  outline-none transition-all placeholder:text-gray-400"
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 px-3 py-2.5 rounded-lg border border-red-100">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-blue-700 text-white text-sm font-medium rounded-lg
                hover:from-blue-700 hover:to-blue-800
                focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-all shadow-sm shadow-blue-200"
            >
              {loading ? 'Signing in...' : 'Enter dashboard'}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-gray-100">
            <p className="text-xs text-center text-gray-400">
              Use <code className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-500 font-mono text-[11px]">admin</code> to preview admin views.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
