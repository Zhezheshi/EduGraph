const API_BASE = '/api';

async function request(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, options);
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`${resp.status}: ${body || resp.statusText}`);
  }
  return resp.json();
}

const api = {
  // Textbooks
  uploadTextbooks: (files) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    return request('/textbooks/upload', { method: 'POST', body: formData });
  },
  getTextbooks: () => request('/textbooks'),
  parseTextbook: (id) => request(`/textbooks/${id}/parse`, { method: 'POST' }),
  parseAll: (force = false) => request(`/textbooks/parse-all?force=${force}`, { method: 'POST' }),
  getTextbook: (id) => request(`/textbooks/${id}`),
  deleteTextbook: (id) => request(`/textbooks/${id}`, { method: 'DELETE' }),

  // Knowledge Graph
  buildKG: (id, opts = {}) => {
    const params = new URLSearchParams();
    if (opts.maxChapters) params.set('max_chapters', opts.maxChapters);
    if (opts.force) params.set('force', 'true');
    const qs = params.toString();
    return request(`/kg/build/${id}${qs ? '?' + qs : ''}`, { method: 'POST' });
  },
  buildAllKG: (opts = {}) => {
    const params = new URLSearchParams();
    if (opts.books) params.set('books', opts.books);
    if (opts.maxChapters) params.set('max_chapters', opts.maxChapters);
    if (opts.force) params.set('force', 'true');
    const qs = params.toString();
    return request(`/pipeline/kg/build-all${qs ? '?' + qs : ''}`, { method: 'POST' });
  },
  getKG: (id) => request(`/kg/${id}`),
  getKGChapters: (id) => request(`/kg/${id}/chapters`),
  getMergedKG: () => request('/kg/merged'),
  getVisualization: () => request('/kg/visualization'),

  // Integration
  runIntegration: (books) => {
    const qs = books ? `?books=${books}` : '';
    return request(`/integration/run${qs}`, { method: 'POST' });
  },
  getDecisions: () => request('/integration/decisions'),
  getDecision: (id) => request(`/integration/decisions/${id}`),
  acceptDecision: (id) => request(`/integration/decisions/${id}/accept`, { method: 'POST' }),
  rejectDecision: (id) => request(`/integration/decisions/${id}/reject`, { method: 'POST' }),
  getStats: () => request('/integration/stats'),

  // RAG
  buildIndex: (opts = {}) => {
    const params = new URLSearchParams();
    if (opts.maxChapters) params.set('max_chapters', opts.maxChapters);
    if (opts.books) params.set('books', opts.books);
    const qs = params.toString();
    return request(`/rag/index${qs ? '?' + qs : ''}`, { method: 'POST' });
  },
  query: (question) => request('/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  }),
  getRagStatus: () => request('/rag/status'),

  // Chat
  sendChat: (message, sessionId = 'default') => request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  }),
  getHistory: (session = 'default') => request(`/chat/history/${session}`),

  // Report
  getReport: () => request('/report'),

  // Pipeline
  getPipelineStatus: () => request('/pipeline/status'),
  health: () => request('/health'),
};

export default api;
