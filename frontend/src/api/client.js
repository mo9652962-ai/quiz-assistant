export class ApiError extends Error {
  constructor(status, message, details = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

function sessionToken() {
  return import.meta.env.VITE_QUIZ_SESSION || localStorage.getItem('quiz-session') || 'local-session'
}

async function readError(response) {
  try {
    const payload = await response.json()
    return new ApiError(response.status, payload.message || payload.detail || '请求失败', payload.details || [])
  } catch {
    return new ApiError(response.status, `请求失败（${response.status}）`)
  }
}

export function createApiClient(fetchImpl = fetch) {
  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {})
    headers.set('X-Quiz-Session', sessionToken())
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const response = await fetchImpl(path, { ...options, headers })
    if (!response.ok) throw await readError(response)
    return response.status === 204 ? null : response.json()
  }

  return {
    health: () => request('/api/health', { headers: { 'X-Quiz-Session': undefined } }),
    banks: () => request('/api/banks'),
    query: (payload) => request('/api/queries', { method: 'POST', body: JSON.stringify(payload) }),
    startPractice: (payload = {}) => request('/api/practice/sessions', {
      method: 'POST', body: JSON.stringify(payload),
    }),
    submitAnswer: (sessionId, payload) => request(`/api/practice/sessions/${sessionId}/answers`, {
      method: 'POST', body: JSON.stringify(payload),
    }),
    reviews: (params = {}) => {
      const query = new URLSearchParams({ limit: String(params.limit || 20) })
      if (params.wrong) query.set('wrong', 'true')
      if (params.due) query.set('due', 'true')
      return request(`/api/reviews?${query}`)
    },
    importQuestions: (file, dryRun) => {
      const form = new FormData()
      form.append('file', file)
      form.append('dry_run', String(dryRun))
      return request('/api/imports', { method: 'POST', body: form })
    },
    ocrRecognize: (files) => {
      const form = new FormData()
      for (const file of files) form.append('files', file)
      return request('/api/ocr/recognize', { method: 'POST', body: form })
    },
    backup: (payload) => request('/api/backups', { method: 'POST', body: JSON.stringify(payload) }),
  }
}

export const api = createApiClient()
