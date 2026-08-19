import { useEffect, useState } from 'react';
import {
  Search, Clock, Cpu, SearchX, Zap, FileText, MessageSquare, KeyRound,
} from 'lucide-react';
import type {
  ActionResolution, SearchResponse, SupportedFormats, TreeResponse,
} from '../api';
import { api } from '../api';
import { Badge, Button, EmptyState, ErrorBanner, Field, inputClass } from '../components/ui';

/** Colour the score so a weak match is obvious at a glance. */
function scoreTone(similarity: number): 'green' | 'amber' | 'red' {
  if (similarity >= 0.7) return 'green';
  if (similarity >= 0.55) return 'amber';
  return 'red';
}

type Mode = 'passages' | 'action';

const confidenceTone: Record<string, 'green' | 'amber' | 'red'> = {
  high: 'green',
  ambiguous: 'amber',
  low: 'red',
};

const confidenceMeaning: Record<string, string> = {
  high: 'The orchestrator would act on the first candidate.',
  ambiguous: 'Too close to call — the orchestrator would ask which one was meant.',
  low: 'Nothing matched well enough. The orchestrator would treat this as a question.',
};

export function SearchSimulator() {
  const [mode, setMode] = useState<Mode>('passages');
  const [resolution, setResolution] = useState<ActionResolution | null>(null);
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [docType, setDocType] = useState('');
  const [folder, setFolder] = useState('');
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formats, setFormats] = useState<SupportedFormats | null>(null);
  const [tree, setTree] = useState<TreeResponse | null>(null);

  useEffect(() => {
    api.formats().then(setFormats).catch(() => {});
    api.tree().then(setTree).catch(() => {});
  }, []);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setResolution(null);

    if (mode === 'action') {
      try {
        setResolution(await api.resolveAction({ message: query, top_k: topK }));
      } catch (err: any) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
      return;
    }

    try {
      setResult(
        await api.search({
          query,
          top_k: topK,
          doc_type: docType || null,
          folder: folder || null,
        }),
      );
    } catch (err: any) {
      setError(err.message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const emptyKnowledgeBase = tree?.total_chunks === 0;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Search Simulator</h1>
        <p className="text-gray-500 mt-1">
          {mode === 'passages'
            ? 'Run a question the way the assistant would, and see exactly which chunks come back.'
            : 'Run an instruction the way the assistant would, and see which API it would call.'}
        </p>
      </div>

      {/* The assistant has two modes and they use retrieval differently, so the
          simulator has to be able to test both. Passage search shows chunks;
          action selection shows the API and the contract behind it. */}
      <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit">
        {([
          ['passages', 'Answer a question', <FileText size={15} key="f" />],
          ['action', 'Take an action', <Zap size={15} key="z" />],
        ] as [Mode, string, React.ReactNode][]).map(([key, label, icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => { setMode(key); setResult(null); setResolution(null); setError(null); }}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === key
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {icon} {label}
          </button>
        ))}
      </div>

      {mode === 'action' && (
        <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-900">
          <Zap size={15} className="shrink-0 mt-0.5" />
          <span>
            Point the knowledge-base switcher at an API catalogue. This runs the same
            resolution the orchestrator would — selection only, nothing is called.
          </span>
        </div>
      )}

      <form onSubmit={run} className="glass-panel p-5 space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                mode === 'action'
                  ? 'e.g. weekend pe 30 percent discount dena hai'
                  : 'e.g. how long does a refund take?'
              }
              className={`${inputClass} pl-10`}
            />
          </div>
          <Button type="submit" variant="primary" loading={busy} icon={<Search size={16} />}>
            {mode === 'action' ? 'Resolve' : 'Search'}
          </Button>
        </div>

        {/* Type and folder narrow a passage search. Action resolution searches
            the whole catalogue by design and infers the domain from the results,
            so those two would be misleading here. */}
        <div className={`grid grid-cols-1 gap-4 ${mode === 'action' ? 'sm:grid-cols-1' : 'sm:grid-cols-3'}`}>
          <Field label="Results">
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className={`${inputClass} bg-white`}
            >
              {[3, 5, 10, 20].map((n) => (
                <option key={n} value={n}>Top {n}</option>
              ))}
            </select>
          </Field>
          {mode === 'passages' && (
            <>
          <Field label="Type">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className={`${inputClass} bg-white`}
            >
              <option value="">All types</option>
              {(formats?.doc_types ?? []).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </Field>
          <Field label="Folder">
            <select
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              className={`${inputClass} bg-white font-mono text-sm`}
            >
              <option value="">All folders</option>
              {(tree?.folders ?? [])
                .filter((f) => f.document_count > 0)
                .map((f) => (
                  <option key={f.path} value={f.path}>{f.path}</option>
                ))}
            </select>
          </Field>
            </>
          )}
        </div>
      </form>

      <ErrorBanner message={error} />

      {result && (
        <div className="space-y-4">
          <div className="flex items-center gap-4 text-sm text-gray-600 flex-wrap">
            <span className="flex items-center gap-1.5">
              <Cpu size={14} className="text-gray-400" />
              <span className="font-mono text-xs">{result.embedding_model}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <Clock size={14} className="text-gray-400" />
              embed <strong className="tabular-nums">{result.embed_ms}ms</strong>
              <span className="text-gray-300">·</span>
              search <strong className="tabular-nums">{result.search_ms}ms</strong>
            </span>
            <span className="ml-auto">{result.total_results} results</span>
          </div>

          {result.results.length === 0 ? (
            <div className="glass-panel">
              <EmptyState icon={<SearchX size={26} />} title="No results">
                {emptyKnowledgeBase
                  ? 'The knowledge base is empty — there is nothing to retrieve yet.'
                  : 'Nothing matched. Try removing the type or folder filter, or check that the relevant document was actually embedded.'}
              </EmptyState>
            </div>
          ) : (
            <div className="space-y-3">
              {result.results.map((hit, index) => (
                <div key={hit.chunk_id} className="glass-panel overflow-hidden">
                  <div className="px-4 py-2.5 bg-gray-50/70 border-b border-gray-100 flex items-center gap-3 flex-wrap">
                    <span className="text-xs font-bold text-gray-400 tabular-nums w-5">
                      #{index + 1}
                    </span>
                    <Badge tone={scoreTone(hit.similarity)}>
                      {hit.similarity.toFixed(4)}
                    </Badge>
                    <span className="font-medium text-gray-900 text-sm truncate">
                      {hit.document_title}
                    </span>
                    <span className="font-mono text-xs text-gray-400 truncate">
                      {hit.folder_path}
                    </span>
                    {typeof hit.metadata?.chunk_kind === 'string' && (
                      // An API card's chunks are a description and a set of
                      // example phrases. Without this label an utterance chunk
                      // reads as a stray line of text.
                      <Badge tone={hit.metadata.chunk_kind === 'utterance' ? 'blue' : 'gray'}>
                        {hit.metadata.chunk_kind === 'utterance' ? (
                          <MessageSquare size={11} className="mr-1" />
                        ) : null}
                        {String(hit.metadata.chunk_kind)}
                      </Badge>
                    )}
                    {typeof hit.metadata?.api_id === 'string' && (
                      <span className="font-mono text-xs text-primary-700">
                        {String(hit.metadata.api_id)}
                      </span>
                    )}
                    <span className="ml-auto text-xs text-gray-500 shrink-0">
                      chunk {hit.chunk_index}
                    </span>
                  </div>
                  <pre className="p-4 whitespace-pre-wrap font-mono text-xs text-gray-700 leading-relaxed max-h-52 overflow-y-auto">
                    {hit.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {resolution && (
        <div className="space-y-4">
          <div className="flex items-center gap-4 text-sm text-gray-600 flex-wrap">
            <Badge tone={confidenceTone[resolution.confidence] ?? 'gray'}>
              {resolution.confidence}
            </Badge>
            <span>{confidenceMeaning[resolution.confidence]}</span>
            <span className="ml-auto flex items-center gap-1.5">
              <Clock size={14} className="text-gray-400" />
              embed <strong className="tabular-nums">{resolution.embed_ms}ms</strong>
              <span className="text-gray-300">·</span>
              search <strong className="tabular-nums">{resolution.search_ms}ms</strong>
            </span>
          </div>

          <p className="text-sm text-gray-600 italic">{resolution.reason}</p>

          {/* How the narrowing went. Shown because a wrong answer is much easier
              to explain when you can see which domains were in play. */}
          <div className="glass-panel p-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Domains considered
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {resolution.domains_ranked.map((d) => (
                <Badge key={d.domain} tone={resolution.domains_kept.includes(d.domain) ? 'green' : 'gray'}>
                  {d.domain} · {d.score.toFixed(3)} · {d.hits}
                </Badge>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Green stayed in play.{' '}
              {resolution.fallback_used
                ? 'Narrowing gave way and the unfiltered ranking was used instead.'
                : resolution.domain_filter_applied
                  ? 'The rest were filtered out.'
                  : 'Everything was already in one group.'}
            </p>
          </div>

          {resolution.candidates.length === 0 ? (
            <div className="glass-panel">
              <EmptyState icon={<SearchX size={26} />} title="Nothing matched">
                No API in this knowledge base came close. Check that the knowledge-base
                switcher is pointed at an API catalogue.
              </EmptyState>
            </div>
          ) : (
            <div className="space-y-3">
              {resolution.candidates.map((candidate, index) => (
                <div key={candidate.api_id} className="glass-panel overflow-hidden">
                  <div className="px-4 py-2.5 bg-gray-50/70 border-b border-gray-100 flex items-center gap-3 flex-wrap">
                    <span className="text-xs font-bold text-gray-400 tabular-nums w-5">
                      #{index + 1}
                    </span>
                    <Badge tone={scoreTone(candidate.score)}>{candidate.score.toFixed(4)}</Badge>
                    <span className="font-mono text-sm text-gray-900">{candidate.api_id}</span>
                    <Badge tone="gray">{candidate.method} {candidate.path}</Badge>
                    {candidate.mpin_required && (
                      <Badge tone="amber">
                        <KeyRound size={11} className="mr-1" /> MPIN
                      </Badge>
                    )}
                  </div>
                  <div className="p-4 space-y-3 text-sm">
                    <p className="text-gray-600 text-xs">
                      matched its{' '}
                      <span className="font-medium">
                        {candidate.matched_kind === 'utterance' ? 'example phrase' : 'description'}
                      </span>
                      {candidate.matched_kind === 'utterance' && (
                        <span className="italic"> “{candidate.matched_text}”</span>
                      )}
                    </p>
                    {candidate.required_fields.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                          Must be collected before calling
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {candidate.required_fields.map((name) => (
                            <code
                              key={name}
                              className="px-2 py-0.5 rounded bg-amber-50 border border-amber-100 text-xs text-amber-800 font-mono"
                            >
                              {name}
                            </code>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-gray-500">
            Every candidate carries its full contract — each field with the sentence to ask
            for it, and each error code in plain words. Open the document to read it, or see
            the <code className="font-mono">contract</code> field in the API response.
          </p>
        </div>
      )}

      {!result && !resolution && !error && (
        <div className="glass-panel">
          <EmptyState icon={<Search size={26} />} title="Run a query">
            This is a spot check on retrieval quality — useful right after adding a document,
            to confirm it actually comes back for the questions it should answer.
          </EmptyState>
        </div>
      )}
    </div>
  );
}
