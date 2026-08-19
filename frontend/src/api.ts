// Single place where the admin UI talks to the service.

const API_BASE = '/api/v1';
const TOKEN_KEY = 'chotu_admin_token';
const KB_KEY = 'chotu_active_kb';

// The session token lives in localStorage. It is scoped to this origin, and the
// alternative — a cookie — would need CSRF protection for no gain on an
// internal tool.
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/** Fires when the server rejects our token, so the app can show the sign-in screen. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler = () => {};

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler;
}

// Which knowledge base this browser is looking at. Sent as a header rather than
// appended to every URL, so it reaches multipart uploads and hand-written calls
// alike without each one having to remember.
export function getActiveKb(): string | null {
  return localStorage.getItem(KB_KEY);
}

export function setActiveKb(slug: string | null): void {
  if (slug) localStorage.setItem(KB_KEY, slug);
  else localStorage.removeItem(KB_KEY);
}

function withAuth(options?: RequestInit): RequestInit {
  const token = getToken();
  const kb = getActiveKb();
  if (!token && !kb) return options ?? {};

  const headers: Record<string, string> = { ...((options?.headers as Record<string, string>) ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (kb) headers['X-Knowledge-Base'] = kb;
  return { ...options, headers };
}

export interface TreeDocument {
  id: string;
  title: string;
  folder_path: string;
  doc_type: string;
  source_format: string;
  file_name: string | null;
  file_size: number | null;
  chunk_count: number;
  embedded_chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface TreeFolder {
  path: string;
  document_count: number;
}

export interface TreeResponse {
  folders: TreeFolder[];
  documents: TreeDocument[];
  total_documents: number;
  total_chunks: number;
}

export interface Chunk {
  id: string;
  chunk_index: number;
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface DocumentDetail extends TreeDocument {
  content: string;
  metadata: Record<string, unknown> | null;
  embedded_chunk_count: number;
  chunks: Chunk[];
}

export interface RecentDocument {
  id: string;
  title: string;
  doc_type: string;
  source_format: string;
  folder_path: string;
  created_at: string;
}

export interface Stats {
  knowledge_base: string;
  total_documents: number;
  total_chunks: number;
  chunks_missing_embedding: number;
  documents_by_type: Record<string, number>;
  documents_by_format: Record<string, number>;
  documents_by_folder: Record<string, number>;
  recent_documents: RecentDocument[];
  embedding_provider: string;
  embedding_model: string;
  configured_dimensions: number;
  stored_dimensions: number | null;
  dimensions_match: boolean;
  chunk_storage_bytes: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  doc_type: string;
  folder_path: string;
  chunk_index: number;
  content: string;
  similarity: number;
  metadata: Record<string, unknown> | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_results: number;
  knowledge_base: string;
  embedding_model: string;
  embed_ms: number;
  search_ms: number;
}

export interface ActionCandidate {
  api_id: string;
  domain: string;
  method: string;
  path: string;
  title: string;
  document_id: string;
  score: number;
  /** 'utterance' when an example phrase matched, 'card' when the description did. */
  matched_kind: string;
  matched_text: string;
  mpin_required: boolean;
  required_fields: string[];
  /** The card's whole front matter — fields with prompts, returns, error messages. */
  contract: Record<string, unknown>;
}

export interface DomainScore {
  domain: string;
  score: number;
  hits: number;
}

export interface ActionResolution {
  query: string;
  knowledge_base: string;
  /** 'high' act · 'ambiguous' ask which · 'low' treat as a question */
  confidence: string;
  reason: string;
  candidates: ActionCandidate[];
  domains_ranked: DomainScore[];
  domains_kept: string[];
  domain_filter_applied: boolean;
  fallback_used: boolean;
  top_score: number | null;
  margin: number | null;
  embed_ms: number;
  search_ms: number;
}

export interface SupportedFormats {
  extensions: string[];
  tabular_formats: string[];
  doc_types: string[];
  max_upload_size_mb: number;
}

export interface EmbeddingSettings {
  knowledge_base: string;
  provider: string;
  model: string;
  dimensions: number;
  batch_size: number;
  requests_per_minute: number;
  chunk_size: number;
  chunk_overlap: number;
  api_key_set: boolean;
  api_key_preview: string | null;
  known_models: string[];
}

export interface ApiKeyUpdateResult {
  ok: boolean;
  message: string;
  api_key_preview: string | null;
  persisted: boolean;
}

export interface LoginResult {
  token: string;
  username: string;
  expires_in_hours: number;
}

export interface CurrentUser {
  auth_enabled: boolean;
  authenticated: boolean;
  username: string | null;
}

export interface DocumentListResponse {
  documents: (TreeDocument & { content: string })[];
  total: number;
  skip: number;
  limit: number;
}

export interface Health {
  status: string;
  database: string;
  version: string;
  environment: string;
}

export interface KnowledgeBase {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  /** user@host:port/database — never the password. */
  dsn_preview: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  chunk_size: number;
  chunk_overlap: number;
  is_default: boolean;
  is_active: boolean;
  /** True when the connection string comes from the server's DATABASE_URL. */
  from_environment: boolean;
  last_error: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseList {
  knowledge_bases: KnowledgeBase[];
  total: number;
  default_slug: string | null;
}

export interface KnowledgeBaseCreate {
  name: string;
  slug?: string;
  description?: string;
  dsn: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface EmbeddingModelOption {
  model: string;
  provider: string;
  allowed_dimensions: number[];
  default_dimensions: number;
  input_token_limit: number;
  multimodal: boolean;
  key_configured: boolean;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
  dsn_preview: string | null;
}

/** Pull the useful message out of a FastAPI error body. */
async function toError(res: Response): Promise<Error> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      // Pydantic validation errors arrive as a list of field errors
      detail = body.detail
        .map((e: any) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`)
        .join('; ');
    } else if (body.error) {
      detail = body.detail ? `${body.error} — ${body.detail}` : body.error;
    }
  } catch {
    // Non-JSON error body; statusText is the best we have
  }
  return new Error(detail);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, withAuth(options));
  if (res.status === 401) {
    // The token is gone or expired. Drop it and let the app show sign-in,
    // rather than leaving every panel showing the same error.
    setToken(null);
    onUnauthorized();
  }
  if (!res.ok) throw await toError(res);
  return res.json();
}

async function postJson<T>(path: string, body: unknown, method = 'POST'): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export const api = {
  tree: () => request<TreeResponse>('/tree'),
  stats: () => request<Stats>('/stats'),
  formats: () => request<SupportedFormats>('/formats'),
  health: async (): Promise<Health> => {
    const res = await fetch('/health', withAuth());
    if (!res.ok) throw await toError(res);
    return res.json();
  },

  me: () => request<CurrentUser>('/auth/me'),

  login: async (username: string, password: string): Promise<LoginResult> => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw await toError(res);
    const result: LoginResult = await res.json();
    setToken(result.token);
    return result;
  },

  logout: async (): Promise<void> => {
    try {
      await request('/auth/logout', { method: 'POST' });
    } finally {
      // Always clear locally, even if the server call fails — otherwise a
      // network blip leaves the user apparently signed in.
      setToken(null);
    }
  },

  embeddingSettings: () => request<EmbeddingSettings>('/settings/embedding'),

  updateApiKey: (api_key: string, persist = true) =>
    postJson<ApiKeyUpdateResult>('/settings/embedding/api-key', { api_key, persist }, 'PUT'),

  listDocuments: (params: {
    folder?: string;
    search?: string;
    doc_type?: string;
    skip?: number;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') query.set(k, String(v));
    });
    return request<DocumentListResponse>(`/documents?${query}`);
  },

  getDocument: (id: string) => request<DocumentDetail>(`/documents/${id}`),

  createDocument: (payload: {
    title: string;
    content: string;
    doc_type: string;
    folder_path: string;
    metadata?: Record<string, unknown> | null;
  }) => postJson<TreeDocument>('/documents', payload),

  updateDocument: (
    id: string,
    payload: Partial<{
      title: string;
      content: string;
      doc_type: string;
      folder_path: string;
      metadata: Record<string, unknown> | null;
    }>,
  ) => postJson<TreeDocument>(`/documents/${id}`, payload, 'PUT'),

  deleteDocument: (id: string) =>
    request<{ message: string }>(`/documents/${id}`, { method: 'DELETE' }),

  uploadDocument: (form: FormData) =>
    request<TreeDocument>('/documents/upload', { method: 'POST', body: form }),

  replaceDocument: (id: string, form: FormData) =>
    request<TreeDocument>(`/documents/${id}/replace`, { method: 'PUT', body: form }),

  search: (payload: {
    query: string;
    top_k: number;
    doc_type?: string | null;
    folder?: string | null;
  }) => postJson<SearchResponse>('/search', payload),

  resolveAction: (payload: { message: string; top_k?: number }) =>
    postJson<ActionResolution>('/actions/resolve', payload),

  // ── Knowledge bases ──

  knowledgeBases: () => request<KnowledgeBaseList>('/knowledge-bases'),

  embeddingModels: () => request<{ models: EmbeddingModelOption[] }>('/embedding-models'),

  testConnection: (dsn: string) =>
    postJson<ConnectionTestResult>('/knowledge-bases/test-connection', { dsn }),

  createKnowledgeBase: (payload: KnowledgeBaseCreate) =>
    postJson<KnowledgeBase>('/knowledge-bases', payload),

  updateKnowledgeBase: (
    slug: string,
    payload: Partial<{
      name: string;
      description: string;
      is_active: boolean;
      make_default: boolean;
      dsn: string;
    }>,
  ) => postJson<KnowledgeBase>(`/knowledge-bases/${slug}`, payload, 'PUT'),

  recheckKnowledgeBase: (slug: string) =>
    postJson<ConnectionTestResult>(`/knowledge-bases/${slug}/check`, {}),

  deleteKnowledgeBase: (slug: string) =>
    request<{ message: string; detail: string | null }>(`/knowledge-bases/${slug}`, {
      method: 'DELETE',
    }),
};

// ── Formatting helpers ──

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** '/a/b/' -> 'b'. The root keeps its slash so it reads as a path, not a name. */
export function folderName(path: string): string {
  if (path === '/') return '/';
  const parts = path.split('/').filter(Boolean);
  return parts[parts.length - 1] ?? '/';
}

/** '/a/b/' -> 2, '/' -> 0. Drives tree indentation. */
export function folderDepth(path: string): number {
  return path.split('/').filter(Boolean).length;
}

/** '/a/b/' -> '/a/'. */
export function parentFolder(path: string): string {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 1) return '/';
  return '/' + parts.slice(0, -1).join('/') + '/';
}

/** Mirror of normalize_folder_path() on the server. */
export function normalizeFolder(path: string): string {
  const parts = (path || '').split('/').map((p) => p.trim()).filter(Boolean);
  return parts.length ? `/${parts.join('/')}/` : '/';
}
