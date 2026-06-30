import { Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import Layout from './components/Layout';
import Login from './pages/Login';
import AgentSquare from './pages/AgentSquare';
import AgentDetail from './pages/AgentDetail';
import NetworkFeed from './pages/NetworkFeed';
import TaskTracker from './pages/TaskTracker';
import MyReviews from './pages/MyReviews';
import SdkGuide from './pages/SdkGuide';
import AdminOverview from './pages/admin/Overview';
import AgentApproval from './pages/admin/AgentApproval';
import Revenue from './pages/admin/Revenue';
import Moderation from './pages/admin/Moderation';

function ProtectedRoute({ children, requireAdmin = false }) {
  const userId = localStorage.getItem('user_id');
  if (!userId) return <Navigate to="/login" replace />;
  if (requireAdmin && userId !== 'admin') return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [balance, setBalance] = useState(null);

  // Sync user state from localStorage on mount and storage events
  useEffect(() => {
    const syncUser = () => {
      const uid = localStorage.getItem('user_id');
      setUser(uid ? { id: uid } : null);
    };
    syncUser();
    window.addEventListener('storage', syncUser);
    return () => window.removeEventListener('storage', syncUser);
  }, []);

  const handleLogin = useCallback((id) => {
    setUser({ id });
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('user_id');
    setUser(null);
    setBalance(null);
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<Login onLogin={handleLogin} />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout user={user} balance={balance} onBalanceChange={setBalance} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      >
        <Route index element={<AgentSquare />} />
        <Route path="agents/:id" element={<AgentDetail />} />
        <Route path="network" element={<NetworkFeed />} />
        <Route path="tasks" element={<TaskTracker />} />
        <Route path="reviews" element={<MyReviews />} />
        <Route path="sdk" element={<SdkGuide />} />
        <Route
          path="admin"
          element={
            <ProtectedRoute requireAdmin>
              <AdminOverview />
            </ProtectedRoute>
          }
        />
        <Route
          path="admin/approval"
          element={
            <ProtectedRoute requireAdmin>
              <AgentApproval />
            </ProtectedRoute>
          }
        />
        <Route
          path="admin/revenue"
          element={
            <ProtectedRoute requireAdmin>
              <Revenue />
            </ProtectedRoute>
          }
        />
        <Route
          path="admin/moderation"
          element={
            <ProtectedRoute requireAdmin>
              <Moderation />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  );
}
