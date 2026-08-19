import { useEffect, useRef, useState } from 'react';
import {
  Trash2,
  Pencil,
  Save,
  XCircle,
  RefreshCw,
  Layers,
  AlertTriangle,
} from 'lucide-react';
import type { DocumentDetail } from '../api';
import { api, formatBytes, formatDate, normalizeFolder } from '../api';
import {
  Badge,
  Button,
  ErrorBanner,
  Field,
  inputClass,
  monoInputClass,
  Spinner,
} from './ui';
import { ApiContract, isApiCard } from './ApiContract';

type Tab = 'contract' | 'content' | 'chunks' | 'metadata';

export function DocumentPanel({
  documentId,
  docTypes,
  extensions,
  onChanged,
  onDeleted,
}: {
  documentId: string;
  docTypes: string[];
  extensions: string[];
  /** Called after a successful write, with the document's current folder so
   *  the tree can reveal it — a move would otherwise hide it in a collapsed
   *  folder and look like the document had disappeared. */
  onChanged: (folderPath: string) => void;
  onDeleted: () => void;
}) {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('content');

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({ title: '', folder_path: '', doc_type: '', content: '' });

  const replaceInput = useRef<HTMLInputElement>(null);
  const [replacing, setReplacing] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDocument(documentId);
      setDoc(data);
      // Open an API card on its contract. Its description is two paragraphs;
      // the contract is what someone opened it to check.
      setTab(isApiCard(data.metadata) ? 'contract' : 'content');
      setDraft({
        title: data.title,
        folder_path: data.folder_path,
        doc_type: data.doc_type,
        content: data.content,
      });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setEditing(false);
    setTab('content');
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  const save = async () => {
    if (!doc) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateDocument(doc.id, {
        title: draft.title,
        folder_path: normalizeFolder(draft.folder_path),
        doc_type: draft.doc_type,
        content: draft.content,
      });
      setEditing(false);
      await load();
      onChanged(normalizeFolder(draft.folder_path));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const replaceFile = async (file: File) => {
    if (!doc) return;
    setReplacing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      await api.replaceDocument(doc.id, form);
      await load();
      onChanged(doc.folder_path);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setReplacing(false);
      if (replaceInput.current) replaceInput.current.value = '';
    }
  };

  const remove = async () => {
    if (!doc) return;
    if (!confirm(`Delete "${doc.title}" and all ${doc.chunk_count} of its chunks?`)) return;
    try {
      await api.deleteDocument(doc.id);
      onDeleted();
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
        <Spinner /> Loading document…
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="p-8">
        <ErrorBanner message={error ?? 'Document could not be loaded.'} />
      </div>
    );
  }

  const contentChanged = draft.content !== doc.content;
  const unembedded = doc.chunk_count === 0 || doc.embedded_chunk_count < doc.chunk_count;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-mono text-gray-500 truncate">{doc.folder_path}</p>
            <h2 className="text-xl font-bold text-gray-900 truncate">{doc.title}</h2>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <Badge tone="blue">{doc.doc_type}</Badge>
              <Badge tone="gray">.{doc.source_format}</Badge>
              <Badge tone={unembedded ? 'amber' : 'green'}>
                {doc.embedded_chunk_count}/{doc.chunk_count} embedded
              </Badge>
            </div>
          </div>

          <div className="flex gap-2 shrink-0">
            {editing ? (
              <>
                <Button icon={<XCircle size={16} />} onClick={() => { setEditing(false); setError(null); load(); }}>
                  Cancel
                </Button>
                <Button variant="primary" icon={<Save size={16} />} loading={saving} onClick={save}>
                  Save
                </Button>
              </>
            ) : (
              <>
                <Button
                  icon={<RefreshCw size={16} />}
                  loading={replacing}
                  onClick={() => replaceInput.current?.click()}
                  title="Replace this document's content with a new file"
                >
                  Replace file
                </Button>
                <Button icon={<Pencil size={16} />} onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button variant="danger" icon={<Trash2 size={16} />} onClick={remove}>
                  Delete
                </Button>
              </>
            )}
          </div>
        </div>

        <input
          ref={replaceInput}
          type="file"
          accept={extensions.join(',')}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) replaceFile(file);
          }}
        />
      </div>

      {/* Facts */}
      <div className="px-6 py-3 border-b border-gray-100 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm bg-gray-50/50 shrink-0">
        <div>
          <p className="text-xs text-gray-500">Source file</p>
          <p className="font-medium text-gray-900 truncate">{doc.file_name ?? '—'}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Size</p>
          <p className="font-medium text-gray-900">{formatBytes(doc.file_size)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Created</p>
          <p className="font-medium text-gray-900">{formatDate(doc.created_at)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Updated</p>
          <p className="font-medium text-gray-900">{formatDate(doc.updated_at)}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-6 border-b border-gray-100 flex gap-1 shrink-0">
        {([
          // An API card leads with its contract. The body is two paragraphs of
          // description; the contract is the part someone opened this to check.
          ...(isApiCard(doc.metadata) ? [['contract', 'Contract'] as [Tab, string]] : []),
          ['content', 'Description'],
          ['chunks', `Chunks (${doc.chunk_count})`],
          ['metadata', 'Raw metadata'],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-4">
        <ErrorBanner message={error} />

        {editing ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Title">
                <input
                  name="title"
                  className={inputClass}
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                />
              </Field>
              <Field label="Type" hint="Changing this re-chunks the document.">
                <select
                  name="doc_type"
                  className={`${inputClass} bg-white`}
                  value={draft.doc_type}
                  onChange={(e) => setDraft({ ...draft, doc_type: e.target.value })}
                >
                  {[...new Set([...docTypes, draft.doc_type])].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Folder path">
              <input
                name="folder_path"
                className={monoInputClass}
                value={draft.folder_path}
                onChange={(e) => setDraft({ ...draft, folder_path: e.target.value })}
              />
            </Field>
            <Field label="Content">
              <textarea
                name="content"
                rows={18}
                className={`${monoInputClass} resize-y`}
                value={draft.content}
                onChange={(e) => setDraft({ ...draft, content: e.target.value })}
              />
            </Field>
            {contentChanged && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-100 rounded-lg text-sm text-amber-800">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>
                  Saving deletes all {doc.chunk_count} chunks and re-embeds the whole document.
                  This takes a few seconds and calls the embedding API once per chunk.
                </span>
              </div>
            )}
          </div>
        ) : tab === 'contract' ? (
          <ApiContract metadata={(doc.metadata ?? {}) as never} />
        ) : tab === 'content' ? (
          <pre className="whitespace-pre-wrap font-mono text-sm text-gray-800 leading-relaxed">
            {doc.content}
          </pre>
        ) : tab === 'chunks' ? (
          doc.chunks.length === 0 ? (
            <p className="text-sm text-gray-500">
              This document produced no chunks, so nothing about it is retrievable.
            </p>
          ) : (
            <div className="space-y-3">
              {doc.chunks.map((chunk) => (
                <div key={chunk.id} className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="px-3 py-2 bg-gray-50 border-b border-gray-100 flex items-center gap-2 text-xs text-gray-600">
                    <Layers size={13} />
                    <span className="font-medium">Chunk {chunk.chunk_index}</span>
                    <span className="text-gray-400">·</span>
                    <span>{chunk.content.length} chars</span>
                  </div>
                  <pre className="p-3 whitespace-pre-wrap font-mono text-xs text-gray-700 leading-relaxed">
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          )
        ) : (
          <pre className="p-3 bg-gray-50 border border-gray-200 rounded-lg font-mono text-xs text-gray-700 overflow-x-auto">
            {JSON.stringify(doc.metadata ?? {}, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
