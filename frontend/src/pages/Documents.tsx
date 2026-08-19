import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FileText, Search, Trash2, ExternalLink } from 'lucide-react';
import type { DocumentListResponse, SupportedFormats, TreeDocument } from '../api';
import { api, formatBytes, formatDate } from '../api';
import { Badge, EmptyState, ErrorBanner, Spinner, inputClass } from '../components/ui';

export function Documents() {
  const [params, setParams] = useSearchParams();
  const folder = params.get('folder') ?? '';
  const [search, setSearch] = useState('');
  const [docType, setDocType] = useState('');
  const [docs, setDocs] = useState<DocumentListResponse['documents']>([]);
  const [total, setTotal] = useState(0);
  const [formats, setFormats] = useState<SupportedFormats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.formats().then(setFormats).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listDocuments({
        limit: 100,
        folder: folder || undefined,
        search: search || undefined,
        doc_type: docType || undefined,
      });
      setDocs(data.documents);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [folder, search, docType]);

  useEffect(() => {
    // Debounced so typing in the search box does not fire a request per keystroke
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const remove = async (doc: TreeDocument) => {
    if (!confirm(`Delete "${doc.title}" and all ${doc.chunk_count} of its chunks?`)) return;
    try {
      await api.deleteDocument(doc.id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">All Documents</h1>
        <p className="text-gray-500 mt-1">
          A flat view of everything in the knowledge base. Use the{' '}
          <Link to="/" className="text-primary-700 hover:underline font-medium">dashboard</Link>{' '}
          to browse by folder or add documents.
        </p>
      </div>

      <ErrorBanner message={error} />

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles and content…"
            className={`${inputClass} pl-9`}
          />
        </div>
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className={`${inputClass} bg-white w-auto`}
        >
          <option value="">All types</option>
          {(formats?.doc_types ?? []).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {folder && (
          <button
            onClick={() => setParams({})}
            className="px-3 py-2 text-sm font-mono bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 transition-colors"
          >
            {folder} ✕
          </button>
        )}
      </div>

      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
            <Spinner /> Loading…
          </div>
        ) : docs.length === 0 ? (
          <EmptyState icon={<FileText size={26} />} title="No documents found">
            {search || docType || folder
              ? 'Nothing matches these filters.'
              : 'Add a document from the dashboard to get started.'}
          </EmptyState>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-600">
                <th className="p-4 pl-6">Document</th>
                <th className="p-4">Folder</th>
                <th className="p-4">Type</th>
                <th className="p-4">Chunks</th>
                <th className="p-4">Updated</th>
                <th className="p-4 pr-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 transition-colors group">
                  <td className="p-4 pl-6">
                    <p className="font-medium text-gray-900">{doc.title}</p>
                    <p className="text-xs text-gray-500">
                      {doc.file_name ?? 'typed in'} · {formatBytes(doc.file_size)}
                    </p>
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => setParams({ folder: doc.folder_path })}
                      className="font-mono text-xs text-gray-600 hover:text-primary-700 hover:underline"
                    >
                      {doc.folder_path}
                    </button>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1.5">
                      <Badge tone="blue">{doc.doc_type}</Badge>
                      <Badge tone="gray">.{doc.source_format}</Badge>
                    </div>
                  </td>
                  <td className="p-4 text-sm text-gray-600 tabular-nums">{doc.chunk_count}</td>
                  <td className="p-4 text-sm text-gray-500">{formatDate(doc.updated_at)}</td>
                  <td className="p-4 pr-6 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link
                        to={`/?doc=${doc.id}`}
                        className="text-primary-700 hover:text-primary-800 text-sm font-medium px-2 py-1 bg-primary-50 rounded flex items-center gap-1"
                      >
                        <ExternalLink size={14} /> Open
                      </Link>
                      <button
                        onClick={() => remove(doc)}
                        className="text-red-600 hover:text-red-800 text-sm font-medium px-2 py-1 bg-red-50 rounded flex items-center gap-1"
                      >
                        <Trash2 size={14} /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!loading && docs.length > 0 && (
        <p className="text-sm text-gray-500">
          Showing {docs.length} of {total} documents.
        </p>
      )}
    </div>
  );
}
