import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FolderPlus,
  FilePlus2,
  UploadCloud,
  RefreshCw,
  Search,
  FolderOpen,
  Database,
  AlertTriangle,
  CheckCircle2,
  Layers,
  FileText,
} from 'lucide-react';
import type { Stats, SupportedFormats, TreeResponse } from '../api';
import { api, formatBytes, formatDate } from '../api';
import { buildTree, pathChain, TreeView } from '../components/Tree';
import type { Selection } from '../components/Tree';
import { DocumentPanel } from '../components/DocumentPanel';
import { AddTextModal, NewFolderModal, UploadModal } from '../components/AddDocument';
import { Badge, Button, EmptyState, ErrorBanner, Spinner, inputClass } from '../components/ui';

function StatCard({
  icon,
  label,
  value,
  tone = 'gray',
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  tone?: 'gray' | 'green' | 'amber' | 'red';
  hint?: string;
}) {
  const tones = {
    gray: 'text-gray-500',
    green: 'text-green-600',
    amber: 'text-amber-600',
    red: 'text-red-600',
  };
  return (
    <div className="glass-panel p-4">
      <div className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${tones[tone]}`}>
        {icon} {label}
      </div>
      {/* Long identifiers (model names) get a smaller size so they do not wrap */}
      <p
        className={`font-bold text-gray-900 mt-1 tabular-nums break-words ${
          typeof value === 'string' && value.length > 12 ? 'text-base' : 'text-2xl'
        }`}
      >
        {value}
      </p>
      {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
    </div>
  );
}

export function Dashboard() {
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [formats, setFormats] = useState<SupportedFormats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [params, setParams] = useSearchParams();
  const [selection, setSelection] = useState<Selection>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['/']));
  const [filter, setFilter] = useState('');
  const [pendingFolders, setPendingFolders] = useState<string[]>([]);

  const [showUpload, setShowUpload] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showNewFolder, setShowNewFolder] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [treeData, statsData, formatData] = await Promise.all([
        api.tree(),
        api.stats(),
        api.formats(),
      ]);
      setTree(treeData);
      setStats(statsData);
      setFormats(formatData);
      // A pending folder stops being pending once a document lands in it
      const realPaths = new Set(treeData.folders.map((f) => f.path));
      setPendingFolders((prev) => prev.filter((p) => !realPaths.has(p)));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Deep link from the All Documents table: /?doc=<id>
  useEffect(() => {
    const wanted = params.get('doc');
    if (!wanted || !tree) return;
    const match = tree.documents.find((d) => d.id === wanted);
    if (match) {
      setExpanded((prev) => new Set([...prev, ...pathChain(match.folder_path)]));
      setSelection({ kind: 'document', id: match.id });
    }
    setParams({}, { replace: true });
  }, [params, tree, setParams]);

  const root = useMemo(
    () => buildTree(tree?.folders ?? [], tree?.documents ?? [], pendingFolders),
    [tree, pendingFolders],
  );

  /** Folder that "add here" targets: the selected folder, or the selected document's. */
  const targetFolder = useMemo(() => {
    if (selection?.kind === 'folder') return selection.path;
    if (selection?.kind === 'document') {
      return tree?.documents.find((d) => d.id === selection.id)?.folder_path ?? '/';
    }
    return '/';
  }, [selection, tree]);

  const toggle = (path: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });

  const revealFolder = (path: string) =>
    setExpanded((prev) => new Set([...prev, ...pathChain(path)]));

  const afterWrite = async (folder: string) => {
    setShowUpload(false);
    setShowAdd(false);
    revealFolder(folder);
    await load();
  };

  const selectedFolderNode = useMemo(() => {
    if (selection?.kind !== 'folder') return null;
    const find = (node: ReturnType<typeof buildTree>): typeof node | null => {
      if (node.path === selection.path) return node;
      for (const child of node.children) {
        const hit = find(child);
        if (hit) return hit;
      }
      return null;
    };
    return find(root);
  }, [selection, root]);

  if (loading) {
    return (
      <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
        <Spinner /> Loading knowledge base…
      </div>
    );
  }

  return (
    <div className="p-8 max-w-[1600px] mx-auto space-y-6">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Knowledge Base</h1>
          <p className="text-gray-500 mt-1">
            Browse the directory, open a document, or add one anywhere in the tree.
          </p>
        </div>
        <Button icon={<RefreshCw size={16} />} onClick={load}>Refresh</Button>
      </div>

      <ErrorBanner message={error} />

      {/* Health */}
      {stats && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={<FileText size={14} />} label="Documents" value={stats.total_documents} />
            <StatCard
              icon={<Layers size={14} />}
              label="Chunks"
              value={stats.total_chunks}
              hint={formatBytes(stats.chunk_storage_bytes) + ' on disk'}
            />
            <StatCard
              icon={stats.chunks_missing_embedding ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
              label="Unembedded"
              value={stats.chunks_missing_embedding}
              tone={stats.chunks_missing_embedding ? 'red' : 'green'}
              hint={stats.chunks_missing_embedding ? 'These chunks are invisible to search' : 'Every chunk is embedded'}
            />
            <StatCard
              icon={stats.dimensions_match ? <Database size={14} /> : <AlertTriangle size={14} />}
              label="Embedding model"
              value={stats.embedding_model}
              tone={stats.dimensions_match ? 'gray' : 'red'}
              hint={
                stats.dimensions_match
                  ? `${stats.configured_dimensions} dims · ${stats.embedding_provider}`
                  : `MISMATCH — config ${stats.configured_dimensions}, stored ${stats.stored_dimensions}`
              }
            />
          </div>

          {!stats.dimensions_match && (
            <div className="flex items-start gap-2 p-4 bg-red-50 border border-red-100 rounded-lg text-sm text-red-800">
              <AlertTriangle size={18} className="shrink-0 mt-0.5" />
              <span>
                Stored vectors are {stats.stored_dimensions} dimensions but the service is
                configured for {stats.configured_dimensions}. Search results will be wrong
                or will fail outright until the knowledge base is re-embedded.
              </span>
            </div>
          )}
        </>
      )}

      {/* Tree + detail */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(280px,360px)_1fr] gap-6 items-start">
        <div className="glass-panel overflow-hidden flex flex-col max-h-[calc(100vh-16rem)]">
          <div className="p-3 border-b border-gray-100 space-y-3 shrink-0">
            <div className="relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter documents…"
                className={`${inputClass} pl-9 py-1.5 text-sm`}
              />
            </div>
            <div className="flex gap-1.5">
              <Button
                className="!px-2.5 !py-1.5 flex-1 justify-center"
                icon={<UploadCloud size={15} />}
                onClick={() => setShowUpload(true)}
                title={`Upload a file into ${targetFolder}`}
              >
                Upload
              </Button>
              <Button
                className="!px-2.5 !py-1.5 flex-1 justify-center"
                icon={<FilePlus2 size={15} />}
                onClick={() => setShowAdd(true)}
                title={`Add a text document to ${targetFolder}`}
              >
                Add
              </Button>
              <Button
                className="!px-2.5 !py-1.5"
                icon={<FolderPlus size={15} />}
                onClick={() => setShowNewFolder(true)}
                title={`New folder inside ${targetFolder}`}
              >
                <span className="sr-only">New folder</span>
              </Button>
            </div>
            <p className="text-xs text-gray-500 truncate">
              Adding to <span className="font-mono text-gray-700">{targetFolder}</span>
            </p>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-2">
            {tree && tree.total_documents === 0 && pendingFolders.length === 0 ? (
              <EmptyState icon={<FolderOpen size={26} />} title="Nothing here yet">
                Upload a file or add a text document to start building the knowledge base.
              </EmptyState>
            ) : (
              <TreeView
                root={root}
                expanded={expanded}
                selection={selection}
                filter={filter}
                onToggle={toggle}
                onSelect={setSelection}
              />
            )}
          </div>
        </div>

        <div className="glass-panel overflow-hidden min-h-[420px] max-h-[calc(100vh-16rem)] flex flex-col">
          {selection?.kind === 'document' ? (
            <DocumentPanel
              documentId={selection.id}
              docTypes={formats?.doc_types ?? ['text']}
              extensions={formats?.extensions ?? []}
              onChanged={async (folderPath) => {
                revealFolder(folderPath);
                await load();
              }}
              onDeleted={() => {
                setSelection(null);
                load();
              }}
            />
          ) : selectedFolderNode ? (
            <div className="p-6 space-y-5 overflow-y-auto min-h-0">
              <div>
                <p className="text-xs font-mono text-gray-500">{selectedFolderNode.path}</p>
                <h2 className="text-xl font-bold text-gray-900">
                  {selectedFolderNode.path === '/' ? 'Knowledge Base' : selectedFolderNode.name}
                </h2>
                <div className="flex gap-2 mt-2">
                  <Badge tone="gray">{selectedFolderNode.totalCount} documents</Badge>
                  <Badge tone="gray">{selectedFolderNode.children.length} subfolders</Badge>
                  {selectedFolderNode.pending && <Badge tone="amber">not saved yet</Badge>}
                </div>
              </div>

              {selectedFolderNode.pending && (
                <p className="text-sm text-gray-600">
                  This folder only exists in your browser. It will be created for real as soon
                  as you add a document to it, and will disappear on refresh if you don't.
                </p>
              )}

              {selectedFolderNode.documents.length > 0 ? (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Documents here</h3>
                  <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                    {selectedFolderNode.documents.map((doc) => (
                      <button
                        key={doc.id}
                        onClick={() => setSelection({ kind: 'document', id: doc.id })}
                        className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-center gap-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-gray-900 truncate">{doc.title}</p>
                          <p className="text-xs text-gray-500">
                            .{doc.source_format} · {doc.chunk_count} chunks · {formatDate(doc.updated_at)}
                          </p>
                        </div>
                        <Badge tone="blue">{doc.doc_type}</Badge>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No documents filed directly in this folder.
                </p>
              )}
            </div>
          ) : (
            <EmptyState icon={<FolderOpen size={26} />} title="Nothing selected">
              Pick a folder or a document from the tree to see it here.
            </EmptyState>
          )}
        </div>
      </div>

      {/* Recent */}
      {stats && stats.recent_documents.length > 0 && (
        <div className="glass-panel p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Recently added</h3>
          <div className="space-y-2">
            {stats.recent_documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => {
                  revealFolder(doc.folder_path);
                  setSelection({ kind: 'document', id: doc.id });
                }}
                className="w-full text-left flex items-center gap-3 text-sm hover:bg-gray-50 rounded-lg px-2 py-1.5 transition-colors"
              >
                <span className="font-medium text-gray-900 truncate">{doc.title}</span>
                <span className="font-mono text-xs text-gray-400 truncate">{doc.folder_path}</span>
                <span className="ml-auto text-xs text-gray-500 shrink-0">
                  {formatDate(doc.created_at)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <UploadModal
        isOpen={showUpload}
        folder={targetFolder}
        formats={formats}
        onClose={() => setShowUpload(false)}
        onDone={afterWrite}
      />
      <AddTextModal
        isOpen={showAdd}
        folder={targetFolder}
        docTypes={formats?.doc_types ?? ['text']}
        onClose={() => setShowAdd(false)}
        onDone={afterWrite}
      />
      <NewFolderModal
        isOpen={showNewFolder}
        parent={targetFolder}
        onClose={() => setShowNewFolder(false)}
        onCreate={(path) => {
          setPendingFolders((prev) => [...new Set([...prev, path])]);
          revealFolder(path);
          setSelection({ kind: 'folder', path });
          setShowNewFolder(false);
        }}
      />
    </div>
  );
}
