import { useState, useEffect } from 'react';
import { getAgents, searchAgents } from '../api/client';
import AgentCard from '../components/AgentCard';

const DOMAINS = ['All', 'analysis.risk', 'analysis.financial', 'supply-chain', 'general'];

const SORT_OPTIONS = [
  { value: 'rating', label: 'Highest rated' },
  { value: 'usage', label: 'Most used' },
  { value: 'newest', label: 'Newest' },
];

export default function AgentSquare() {
  const [agents, setAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [domain, setDomain] = useState('All');
  const [sortBy, setSortBy] = useState('rating');

  const loadAgents = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAgents({ domain: domain === 'All' ? undefined : domain, sort_by: sortBy });
      setAgents(Array.isArray(res) ? res : res?.agents || []);
    } catch (err) {
      setError('Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, [domain, sortBy]);

  const handleSearch = async () => {
    if (!searchText.trim()) {
      loadAgents();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await searchAgents(searchText, domain === 'All' ? undefined : domain, 20);
      setAgents(res?.matches || []);
    } catch (err) {
      setError('Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Agent Square</h1>
        <p className="mt-2 text-gray-500">Discover registered agents and inspect their capabilities.</p>
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="flex-1 min-w-[240px]">
          <div className="relative">
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search agents by capability or domain..."
              className="w-full px-4 py-2.5 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <svg
              className="absolute left-3 top-3 h-5 w-5 text-gray-400 cursor-pointer"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              onClick={handleSearch}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="px-4 py-2.5 border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {DOMAINS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-4 py-2.5 border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="flex justify-center items-center py-20">
          <div className="flex items-center gap-3 text-blue-600">
            <svg className="animate-spin h-6 w-6" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Loading agents...</span>
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="flex flex-col items-center justify-center py-20">
          <p className="text-red-500 text-lg mb-4">{error}</p>
          <button
            onClick={loadAgents}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {agents && !loading && (
        <p className="text-sm text-gray-500 mb-4">
          {agents.length} agent{agents.length === 1 ? '' : 's'} available
        </p>
      )}

      {agents && !loading && !error && (
        <>
          {agents.length === 0 ? (
            <div className="flex justify-center items-center py-20">
              <p className="text-gray-400 text-lg">No agents registered yet</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {agents.map((agent) => (
                <AgentCard key={agent.id || agent.agent_id} agent={agent} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
