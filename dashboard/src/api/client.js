import axios from 'axios';

const API_BASE = '/api/v1';
const STORAGE_KEY = 'user_id';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// --- User ID helpers ---

export function getUserId() {
  return localStorage.getItem(STORAGE_KEY);
}

function setUserId(id) {
  localStorage.setItem(STORAGE_KEY, id);
}

export function clearUserId() {
  localStorage.removeItem(STORAGE_KEY);
}

// --- Auth ---

export async function login(userId) {
  try {
    setUserId(userId);
    return { user_id: userId };
  } catch (err) {
    console.error('[API] login error:', err);
    return null;
  }
}

export function logout() {
  clearUserId();
}

// --- Internal helpers ---

function withUser(extra = {}) {
  const uid = getUserId();
  if (uid) extra.user_id = uid;
  return extra;
}

async function get(path, params = {}) {
  try {
    const res = await api.get(path, { params: withUser(params) });
    return res.data;
  } catch (err) {
    console.error(`[API] GET ${path} error:`, err?.response?.data || err.message);
    return null;
  }
}

async function post(path, data = {}) {
  try {
    const res = await api.post(path, withUser(data));
    return res.data;
  } catch (err) {
    console.error(`[API] POST ${path} error:`, err?.response?.data || err.message);
    return null;
  }
}

// --- Agents ---

export async function getAgents(params = {}) {
  return get('/agents', params);
}

export async function getAgent(id) {
  return get(`/agents/${id}`);
}

export async function searchAgents(description, domains, top_k = 10) {
  const domainList = Array.isArray(domains) ? domains : domains ? [domains] : [];
  return post('/discovery/search', { description, domains: domainList, top_k });
}

// --- Sessions ---

export async function getSessions(limit = 20) {
  return get('/collaboration/sessions', { limit });
}

export async function getSession(id) {
  return get(`/collaboration/sessions/${id}`);
}

export async function getSessionMessages(id) {
  return get(`/collaboration/sessions/${id}/messages`);
}

// --- Reviews ---

export async function submitReview(agent_id, task_id, rating, text) {
  return post('/reviews', { agent_id, task_id, rating, review_text: text });
}

export async function getReviews(user_id) {
  try {
    const res = await api.get(`/users/${encodeURIComponent(user_id)}/reviews`);
    return res.data;
  } catch (err) {
    console.error('[API] getReviews error:', err?.response?.data || err.message);
    return null;
  }
}

// --- Billing ---

export async function getBillingAccount() {
  return get('/billing/account');
}

// --- Admin ---

export async function getAdminOverview() {
  return get('/admin/overview');
}

export async function getAdminPendingAgents() {
  return get('/admin/agents/pending');
}

export async function approveAgent(id) {
  return post(`/admin/agents/${id}/approve`);
}

export async function rejectAgent(id) {
  return post(`/admin/agents/${id}/reject`);
}

export async function getAllAdminAgents() {
  return get('/admin/agents/all');
}

export async function getAdminRevenue(days = 30) {
  return get('/admin/revenue', { days });
}

export async function getAdminFlaggedReviews() {
  return get('/admin/reviews/flagged');
}

async function del(path) {
  try {
    const res = await api.delete(path, { params: withUser() });
    return res.data;
  } catch (err) {
    console.error(`[API] DELETE ${path} error:`, err?.response?.data || err.message);
    return null;
  }
}

export async function deleteAdminReview(id) {
  return del(`/admin/reviews/${id}`);
}
