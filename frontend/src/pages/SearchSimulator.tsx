import { useEffect, useState } from 'react';
import { Search, Clock, Cpu, SearchX } from 'lucide-react';
import type { SearchResponse, SupportedFormats, TreeResponse } from '../api';
import { api } from '../api';
import { Badge, Button, EmptyState, ErrorBanner, Field, inputClass } from '../components/ui';

/** Colour the score so a weak match is obvious at a glance. */
function scoreTone(similarity: number): 'green' | 'amber' | 'red' {
  if (similarity >= 0.7) return 'green';
  if (similarity >= 0.55) return 'amber';
  return 'red';
}

export function SearchSimulator() {
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
          Run a question the way the assistant would, and see exactly which chunks come back.
        </p>
      </div>

      <form onSubmit={run} className="glass-panel p-5 space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. how long does a refund take?"
              className={`${inputClass} pl-10`}
            />
          </div>
          <Button type="submit" variant="primary" loading={busy} icon={<Search size={16} />}>
            Search
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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

      {!result && !error && (
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
