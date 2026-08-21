import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Lock,
  Plug,
  Plus,
  Server,
  Star,
  Trash2,
} from 'lucide-react';
import type {
  ConnectionTestResult,
  EmbeddingModelOption,
  KnowledgeBase,
} from '../api';
import { api, formatDate } from '../api';
import {
  Badge,
  Button,
  EmptyState,
  ErrorBanner,
  Field,
  Modal,
  Spinner,
  inputClass,
  monoInputClass,
} from '../components/ui';

/**
 * The create form.
 *
 * The model dropdown only exists here, and that is deliberate: every vector in a
 * knowledge base is produced by one model, and vectors from two models are not
 * comparable. Changing it later would need a re-ingest, so it is a decision made
 * once, at the point the knowledge base is created.
 */
function CreateForm({
  models,
  onCreated,
  onClose,
}: {
  models: EmbeddingModelOption[];
  onCreated: (kb: KnowledgeBase) => void;
  onClose: () => void;
}) {
  const usable = models.filter((m) => m.key_configured);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  // Almost every knowledge base lives in this service's own database, so that is
  // the default and it asks for nothing. A different host is the exception.
  const [elsewhere, setElsewhere] = useState(false);
  const [dsn, setDsn] = useState('');
  const [model, setModel] = useState(usable[0]?.model ?? models[0]?.model ?? '');
  const [dimensions, setDimensions] = useState(
    usable[0]?.default_dimensions ?? models[0]?.default_dimensions ?? 3072,
  );
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<ConnectionTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = models.find((m) => m.model === model);

  // undefined tells the server "your own database" — it stores nothing and reads
  // DATABASE_URL on every connect.
  const fullDsn = () => (elsewhere ? dsn.trim() || undefined : undefined);

  const chooseModel = (next: string) => {
    setModel(next);
    const spec = models.find((m) => m.model === next);
    if (spec) setDimensions(spec.default_dimensions);
  };

  const runTest = async () => {
    setTesting(true);
    setTest(null);
    try {
      // Only reachable while a remote host is being entered; the service's own
      // database needs no test, it is already connected.
      setTest(await api.testConnection(dsn.trim()));
    } catch (e: any) {
      setTest({ ok: false, message: e.message, dsn_preview: null });
    } finally {
      setTesting(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onCreated(
        await api.createKnowledgeBase({
          name: name.trim(),
          description: description.trim() || undefined,
          dsn: fullDsn(),
          embedding_provider: selected?.provider ?? 'gemini',
          embedding_model: model,
          embedding_dimensions: dimensions,
        }),
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-5">
      <ErrorBanner message={error} />

      <Field label="Name" hint="Shown in the switcher. The identifier is derived from it.">
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Merchant Ops"
          className={inputClass}
          required
        />
      </Field>

      <Field label="Description" hint="Optional — what belongs in this knowledge base.">
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Support runbooks for the ops team"
          className={inputClass}
        />
      </Field>

      <div className="border-t border-gray-100 pt-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Server size={15} /> Where the documents live
        </h3>

        <div className="space-y-2">
          <label className="flex items-start gap-2.5 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50">
            <input
              type="radio"
              checked={!elsewhere}
              onChange={() => {
                setElsewhere(false);
                setTest(null);
              }}
              className="mt-0.5"
            />
            <span className="text-sm">
              <span className="font-medium text-gray-900">
                In this service&rsquo;s database
              </span>
              <span className="block text-xs text-gray-500 mt-0.5">
                Gets its own pair of tables alongside the others. Nothing to configure,
                and no connection string is stored — so rotating the database password
                stays a change to the server&rsquo;s <code>.env</code>.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-2.5 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50">
            <input
              type="radio"
              checked={elsewhere}
              onChange={() => {
                setElsewhere(true);
                setTest(null);
              }}
              className="mt-0.5"
            />
            <span className="text-sm">
              <span className="font-medium text-gray-900">On a different Postgres host</span>
              <span className="block text-xs text-gray-500 mt-0.5">
                For a knowledge base that has to live on its own server.
              </span>
            </span>
          </label>
        </div>

        {elsewhere && (
          <>
            <Field
              label="Postgres connection string"
              hint="Needs the pgvector extension. Stored encrypted on the server and never sent back to this page."
            >
              <input
                value={dsn}
                onChange={(e) => {
                  setDsn(e.target.value);
                  setTest(null);
                }}
                placeholder="postgresql://user:password@host:5432/database"
                className={monoInputClass}
                required
                autoComplete="off"
              />
            </Field>

            <div className="flex items-start gap-3">
              <Button
                type="button"
                onClick={runTest}
                loading={testing}
                disabled={!dsn.trim()}
                icon={<Plug size={16} />}
              >
                {testing ? 'Connecting…' : 'Test connection'}
              </Button>
              {test && (
                <div
                  className={`flex-1 p-2.5 rounded-lg border text-sm ${
                    test.ok
                      ? 'bg-green-50 border-green-100 text-green-800'
                      : 'bg-red-50 border-red-100 text-red-700'
                  }`}
                >
                  {test.message}
                </div>
              )}
            </div>

            <p className="text-xs text-gray-500 flex items-start gap-1.5">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>
                The host must be reachable from the server, not from your laptop. If it
                sits behind SSH, run the tunnel on the server and point this at the local
                end of it.
              </span>
            </p>
          </>
        )}
      </div>

      <div className="border-t border-gray-100 pt-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Database size={15} /> How the documents are embedded
        </h3>

        <Field
          label="Embedding model"
          hint="Fixed once the knowledge base exists. Changing it later would invalidate every vector in it, so it needs a re-ingest rather than an edit."
        >
          <select
            value={model}
            onChange={(e) => chooseModel(e.target.value)}
            className={inputClass}
            required
          >
            {models.map((m) => (
              <option key={m.model} value={m.model} disabled={!m.key_configured}>
                {m.model} · {m.provider}
                {m.key_configured ? '' : ' — no API key configured on the server'}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Dimensions"
          hint={
            selected
              ? `${selected.model} accepts ${selected.allowed_dimensions.join(', ')}. Fewer dimensions means smaller storage and slightly weaker retrieval.`
              : undefined
          }
        >
          <select
            value={dimensions}
            onChange={(e) => setDimensions(Number(e.target.value))}
            className={inputClass}
          >
            {(selected?.allowed_dimensions ?? [3072]).map((d) => (
              <option key={d} value={d}>
                {d}
                {d === selected?.default_dimensions ? ' (full)' : ''}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
        <Button type="button" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={saving} icon={<Plus size={16} />}>
          {saving ? 'Connecting and creating…' : 'Add knowledge base'}
        </Button>
      </div>
    </form>
  );
}

function KbCard({
  kb,
  active,
  onSwitch,
  onChanged,
}: {
  kb: KnowledgeBase;
  active: boolean;
  onSwitch: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const recheck = () =>
    act(async () => {
      const result = await api.recheckKnowledgeBase(kb.slug);
      if (!result.ok) setError(result.message);
    });

  const remove = () => {
    if (
      !confirm(
        `Remove "${kb.name}" from the list?\n\nIts documents and vectors stay exactly where they are — only this service stops pointing at them.`,
      )
    )
      return;
    act(() => api.deleteKnowledgeBase(kb.slug));
  };

  return (
    <div
      className={`glass-panel p-5 ${active ? 'ring-2 ring-primary-500' : ''}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-gray-900 truncate">{kb.name}</h3>
            {kb.is_default && (
              <Badge tone="blue">
                <Star size={11} className="mr-1" /> default
              </Badge>
            )}
            {active && <Badge tone="green">viewing</Badge>}
            {!kb.is_active && <Badge tone="gray">deactivated</Badge>}
            {kb.last_error && (
              <Badge tone="red">
                <AlertTriangle size={11} className="mr-1" /> unreachable
              </Badge>
            )}
          </div>
          <p className="text-xs text-gray-500 font-mono mt-1">{kb.slug}</p>
          {kb.description && (
            <p className="text-sm text-gray-600 mt-2">{kb.description}</p>
          )}
        </div>

        <div className="flex gap-2 shrink-0">
          {!active && kb.is_active && (
            <Button onClick={onSwitch}>Switch to</Button>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 mt-4 text-sm">
        <div>
          <dt className="text-gray-500 text-xs">Database</dt>
          <dd className="font-mono text-xs text-gray-900 break-all">{kb.dsn_preview}</dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Tables</dt>
          <dd className="font-mono text-xs text-gray-900 break-all">
            {kb.table_prefix}_documents · {kb.table_prefix}_chunks
          </dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Model</dt>
          <dd className="font-mono text-xs text-gray-900">
            {kb.embedding_model} · {kb.embedding_dimensions}d
          </dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Chunking</dt>
          <dd className="text-xs text-gray-900">
            {kb.chunk_size} chars, {kb.chunk_overlap} overlap
          </dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Added</dt>
          <dd className="text-xs text-gray-900">{formatDate(kb.created_at)}</dd>
        </div>
      </dl>

      {kb.from_environment && kb.is_default && (
        <p className="mt-3 text-xs text-gray-500 flex items-start gap-1.5">
          <Lock size={12} className="shrink-0 mt-0.5" />
          Configured in the server's environment. Its connection string and model are
          changed there, not here.
        </p>
      )}

      {kb.from_environment && !kb.is_default && (
        <p className="mt-3 text-xs text-gray-500 flex items-start gap-1.5">
          <Lock size={12} className="shrink-0 mt-0.5" />
          Lives in this service's own database. No connection string is stored for it, so
          it follows the server's <code>DATABASE_URL</code> if that changes.
        </p>
      )}

      {kb.last_error && (
        <div className="mt-3 p-2.5 rounded-lg border border-red-100 bg-red-50 text-xs text-red-700">
          <p>{kb.last_error}</p>
          <p className="mt-1 text-red-600/80">
            Last checked {kb.last_checked_at ? formatDate(kb.last_checked_at) : 'at startup'}.
            Re-check once the host is back.
          </p>
        </div>
      )}

      <ErrorBanner message={error} />

      {!kb.from_environment && (
        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-100">
          <Button onClick={recheck} loading={busy} icon={<Plug size={15} />}>
            Re-check
          </Button>
          {!kb.is_default && kb.is_active && (
            <Button
              onClick={() => act(() => api.updateKnowledgeBase(kb.slug, { make_default: true }))}
              loading={busy}
              icon={<Star size={15} />}
            >
              Make default
            </Button>
          )}
          <Button
            onClick={() =>
              act(() => api.updateKnowledgeBase(kb.slug, { is_active: !kb.is_active }))
            }
            loading={busy}
          >
            {kb.is_active ? 'Deactivate' : 'Reactivate'}
          </Button>
          <Button onClick={remove} variant="danger" loading={busy} icon={<Trash2 size={15} />}>
            Remove
          </Button>
        </div>
      )}
    </div>
  );
}

export function KnowledgeBases({
  knowledgeBases,
  reload,
  activeKb,
  onSwitch,
}: {
  knowledgeBases: KnowledgeBase[];
  /** Refreshes the list App holds, so the sidebar switcher stays in step. */
  reload: () => Promise<void>;
  activeKb: string | null;
  onSwitch: (slug: string) => void;
}) {
  const [models, setModels] = useState<EmbeddingModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  // The list itself lives in App, because the sidebar switcher renders from it
  // too. Keeping a second copy here is how adding one stopped showing up in the
  // switcher until a reload.
  const load = () => {
    setLoading(true);
    Promise.allSettled([reload(), api.embeddingModels()])
      .then(([kbs, ms]) => {
        if (kbs.status === 'rejected') setError(kbs.reason?.message ?? String(kbs.reason));
        else setError(null);
        if (ms.status === 'fulfilled') setModels(ms.value.models);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const list = knowledgeBases;
  const current = activeKb ?? list.find((kb) => kb.is_default)?.slug ?? null;

  if (loading && list.length === 0) {
    return (
      <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
        <Spinner /> Loading knowledge bases…
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Knowledge bases</h1>
          <p className="text-gray-500 mt-1">
            Each one is its own pgvector database and its own embedding model.
          </p>
        </div>
        <Button variant="primary" onClick={() => setAdding(true)} icon={<Plus size={16} />}>
          Add knowledge base
        </Button>
      </div>

      <ErrorBanner message={error} />

      <div className="flex items-start gap-2 p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-900">
        <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
        <span>
          Documents, folders and search results never cross between knowledge bases. The one
          you are viewing is the one every other page acts on.
        </span>
      </div>

      {list.length === 0 ? (
        <EmptyState icon={<Database size={26} />} title="No knowledge bases yet">
          Restart the service to register the one from its environment.
        </EmptyState>
      ) : (
        <div className="space-y-4">
          {list.map((kb) => (
            <KbCard
              key={kb.id}
              kb={kb}
              active={kb.slug === current}
              onSwitch={() => onSwitch(kb.slug)}
              onChanged={load}
            />
          ))}
        </div>
      )}

      <Modal title="Add a knowledge base" isOpen={adding} onClose={() => setAdding(false)} wide>
        <CreateForm
          models={models}
          onClose={() => setAdding(false)}
          onCreated={(kb) => {
            setAdding(false);
            load();
            onSwitch(kb.slug);
          }}
        />
      </Modal>
    </div>
  );
}
