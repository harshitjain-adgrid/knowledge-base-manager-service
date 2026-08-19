import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, Lock, Save } from 'lucide-react';
import type { EmbeddingSettings, Health, Stats, SupportedFormats } from '../api';
import { api, formatBytes } from '../api';
import { Badge, Button, ErrorBanner, Field, Spinner, inputClass } from '../components/ui';

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900 text-right">{children}</span>
    </div>
  );
}

function ApiKeyCard({
  embedding,
  onUpdated,
}: {
  embedding: EmbeddingSettings;
  onUpdated: (preview: string | null) => void;
}) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await api.updateApiKey(value.trim());
      setResult({
        ok: true,
        text: r.persisted
          ? `${r.message} Saved to .env, so it survives a restart.`
          : r.message,
      });
      setValue('');
      onUpdated(r.api_key_preview);
    } catch (err: any) {
      setResult({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-5">
      <h2 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-2">
        <KeyRound size={15} /> {embedding.provider} API key
      </h2>

      <Row label="Currently loaded">
        {embedding.api_key_set ? (
          <span className="font-mono text-xs">{embedding.api_key_preview}</span>
        ) : (
          <Badge tone="red">not set</Badge>
        )}
      </Row>

      <form onSubmit={submit} className="pt-4 space-y-3">
        <Field
          label="Replace key"
          hint="Checked against the provider before it is accepted, so a bad key cannot replace a working one."
        >
          <div className="flex gap-2">
            <input
              type="password"
              autoComplete="off"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Paste a new API key"
              className={`${inputClass} font-mono text-sm`}
            />
            <Button type="submit" variant="primary" loading={busy} icon={<Save size={16} />}>
              {busy ? 'Verifying…' : 'Save'}
            </Button>
          </div>
        </Field>

        {result && (
          <div
            className={`p-3 rounded-lg border text-sm ${
              result.ok
                ? 'bg-green-50 border-green-100 text-green-800'
                : 'bg-red-50 border-red-100 text-red-700'
            }`}
          >
            {result.text}
          </div>
        )}
      </form>
    </div>
  );
}

export function Settings() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [formats, setFormats] = useState<SupportedFormats | null>(null);
  const [embedding, setEmbedding] = useState<EmbeddingSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Settled independently rather than with Promise.all: one endpoint being
    // unreachable should cost its own panel, not the entire page.
    Promise.allSettled([api.stats(), api.health(), api.formats(), api.embeddingSettings()])
      .then(([statsResult, healthResult, formatsResult, embeddingResult]) => {
        if (statsResult.status === 'fulfilled') setStats(statsResult.value);
        if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
        if (formatsResult.status === 'fulfilled') setFormats(formatsResult.value);
        if (embeddingResult.status === 'fulfilled') setEmbedding(embeddingResult.value);

        const failed = [statsResult, healthResult, formatsResult, embeddingResult]
          .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
          .map((r) => r.reason?.message ?? String(r.reason));
        if (failed.length) setError(failed.join('\n'));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
        <Spinner /> Loading settings…
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">
          {embedding
            ? `Configuration for the "${embedding.knowledge_base}" knowledge base, read from the server.`
            : "The service's active configuration, read from the server."}
        </p>
      </div>

      <ErrorBanner message={error} />

      <div className="flex items-start gap-2 p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-900">
        <Lock size={16} className="shrink-0 mt-0.5" />
        <span>
          The API key can be replaced here, and applies to every knowledge base using this
          provider. Model and dimensions belong to the knowledge base and cannot be changed,
          because changing either invalidates every vector it holds — see the note at the
          bottom.
        </span>
      </div>

      {embedding && (
        <ApiKeyCard
          embedding={embedding}
          onUpdated={(preview) =>
            setEmbedding({ ...embedding, api_key_set: true, api_key_preview: preview })
          }
        />
      )}

      {stats && (
        <div className="glass-panel p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Embeddings</h2>
          <Row label="Knowledge base">
            <span className="font-mono text-xs">{stats.knowledge_base}</span>
          </Row>
          <Row label="Provider">{stats.embedding_provider}</Row>
          <Row label="Model"><span className="font-mono text-xs">{stats.embedding_model}</span></Row>
          <Row label="Configured dimensions">{stats.configured_dimensions}</Row>
          <Row label="Dimensions in the database">
            {stats.stored_dimensions ?? <span className="text-gray-400">no vectors yet</span>}
          </Row>
          <Row label="Consistent">
            {stats.dimensions_match ? (
              <Badge tone="green">
                <CheckCircle2 size={12} className="mr-1" /> matched
              </Badge>
            ) : (
              <Badge tone="red">
                <AlertTriangle size={12} className="mr-1" /> mismatch
              </Badge>
            )}
          </Row>
        </div>
      )}

      {health && (
        <div className="glass-panel p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Service</h2>
          <Row label="Status">
            <Badge tone={health.status === 'healthy' ? 'green' : 'red'}>{health.status}</Badge>
          </Row>
          <Row label="Database">
            <Badge tone={health.database === 'connected' ? 'green' : 'red'}>{health.database}</Badge>
          </Row>
          <Row label="Environment">{health.environment}</Row>
          <Row label="Version">{health.version}</Row>
        </div>
      )}

      {stats && (
        <div className="glass-panel p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Content</h2>
          <Row label="Documents">{stats.total_documents}</Row>
          <Row label="Chunks">{stats.total_chunks}</Row>
          <Row label="Chunks missing an embedding">
            {stats.chunks_missing_embedding === 0 ? (
              <Badge tone="green">none</Badge>
            ) : (
              <Badge tone="red">{stats.chunks_missing_embedding}</Badge>
            )}
          </Row>
          <Row label="Vector storage">{formatBytes(stats.chunk_storage_bytes)}</Row>
          <Row label="By format">
            <span className="font-mono text-xs">
              {Object.entries(stats.documents_by_format)
                .map(([k, v]) => `${k}:${v}`)
                .join('  ') || '—'}
            </span>
          </Row>
        </div>
      )}

      {formats && (
        <div className="glass-panel p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Uploads</h2>
          <Row label="Accepted file types">
            <span className="font-mono text-xs">{formats.extensions.join(' ')}</span>
          </Row>
          <Row label="Maximum size">{formats.max_upload_size_mb} MB</Row>
          <Row label="Document types">
            <span className="font-mono text-xs">{formats.doc_types.join(' ')}</span>
          </Row>
        </div>
      )}

      <div className="glass-panel p-5 text-sm text-gray-600 space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">Changing the embedding model</h2>
        <p>
          Vectors from two different models are not comparable — the same sentence embedded
          by <span className="font-mono text-xs">gemini-embedding-001</span> and{' '}
          <span className="font-mono text-xs">gemini-embedding-2</span> scores near zero
          cosine similarity against itself.
        </p>
        <p>
          So switching models means re-embedding every chunk, not flipping a setting. The
          model is therefore chosen once, when a knowledge base is created, and is fixed
          from then on. To move to a different model, add a new knowledge base on the{' '}
          <span className="font-mono text-xs">Knowledge Bases</span> page and re-ingest into
          it — both stay searchable while you do.
        </p>
        <p>
          The default knowledge base is the exception: its model comes from the server's{' '}
          <span className="font-mono text-xs">.env</span>, because that is where it has
          always been configured.
        </p>
      </div>
    </div>
  );
}
