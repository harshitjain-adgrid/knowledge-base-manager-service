import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  FileText,
  FileSpreadsheet,
  FileCode2,
  Presentation,
  Globe,
  FileType2,
  AlertTriangle,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { TreeDocument, TreeFolder } from '../api';
import { folderName, folderDepth } from '../api';

export interface FolderNode {
  path: string;
  name: string;
  children: FolderNode[];
  documents: TreeDocument[];
  /** Documents filed directly here. */
  directCount: number;
  /** Documents here and in every descendant — what the folder badge shows. */
  totalCount: number;
  /** Folder the user created in the UI that holds no documents yet. */
  pending: boolean;
}

export type Selection =
  | { kind: 'folder'; path: string }
  | { kind: 'document'; id: string }
  | null;

/**
 * Assemble the nested tree from the flat payload.
 *
 * Folders are derived from document paths server-side (including intermediate
 * levels), so the only thing added here is `pendingFolders` — folders the admin
 * just created in the UI, which have no documents yet and therefore do not
 * exist server-side until something is filed in them.
 */
export function buildTree(
  folders: TreeFolder[],
  documents: TreeDocument[],
  pendingFolders: string[] = [],
): FolderNode {
  const nodes = new Map<string, FolderNode>();

  const ensure = (path: string, pending: boolean): FolderNode => {
    let node = nodes.get(path);
    if (!node) {
      node = {
        path,
        name: folderName(path),
        children: [],
        documents: [],
        directCount: 0,
        totalCount: 0,
        pending,
      };
      nodes.set(path, node);
    } else if (!pending) {
      node.pending = false;
    }
    return node;
  };

  /**
   * Create a folder and every folder above it.
   *
   * Always walking the whole chain matters: a node whose parent is missing
   * cannot be linked, and would drop out of the tree along with its documents.
   * The server does send intermediate folders, but the tree must not depend on
   * that to avoid losing documents silently.
   */
  const ensureChain = (path: string, pending: boolean): FolderNode => {
    let node = ensure('/', false);
    let current = '';
    path
      .split('/')
      .filter(Boolean)
      .forEach((part) => {
        current += `/${part}`;
        node = ensure(`${current}/`, pending);
      });
    return node;
  };

  ensure('/', false);
  folders.forEach((f) => ensureChain(f.path, false));
  pendingFolders.forEach((path) => ensureChain(path, true));
  documents.forEach((doc) => {
    ensureChain(doc.folder_path, false).documents.push(doc);
  });

  // Link children to parents. Sorting by depth guarantees a parent exists first.
  const paths = [...nodes.keys()].sort(
    (a, b) => folderDepth(a) - folderDepth(b) || a.localeCompare(b),
  );
  paths.forEach((path) => {
    if (path === '/') return;
    const parts = path.split('/').filter(Boolean);
    const parentPath = parts.length <= 1 ? '/' : `/${parts.slice(0, -1).join('/')}/`;
    const parent = nodes.get(parentPath);
    if (parent) parent.children.push(nodes.get(path)!);
  });

  // Roll counts up from the leaves
  const tally = (node: FolderNode): number => {
    node.directCount = node.documents.length;
    node.documents.sort((a, b) => a.title.localeCompare(b.title));
    node.children.sort((a, b) => a.name.localeCompare(b.name));
    node.totalCount =
      node.directCount + node.children.reduce((sum, child) => sum + tally(child), 0);
    return node.totalCount;
  };

  const root = nodes.get('/')!;
  tally(root);
  return root;
}

const FORMAT_ICONS: Record<string, ReactNode> = {
  pdf: <FileType2 size={15} className="text-red-500" />,
  docx: <FileText size={15} className="text-blue-500" />,
  pptx: <Presentation size={15} className="text-orange-500" />,
  html: <Globe size={15} className="text-teal-600" />,
  md: <FileCode2 size={15} className="text-purple-500" />,
  json: <FileCode2 size={15} className="text-amber-600" />,
  csv: <FileSpreadsheet size={15} className="text-emerald-600" />,
  xlsx: <FileSpreadsheet size={15} className="text-emerald-600" />,
};

function formatIcon(format: string): ReactNode {
  return FORMAT_ICONS[format] ?? <FileText size={15} className="text-gray-400" />;
}

/** Every folder path from the root down to `path`, so it can be revealed. */
export function pathChain(path: string): string[] {
  const chain = ['/'];
  let current = '';
  path
    .split('/')
    .filter(Boolean)
    .forEach((part) => {
      current += `/${part}`;
      chain.push(`${current}/`);
    });
  return chain;
}

function matches(doc: TreeDocument, filter: string): boolean {
  const needle = filter.toLowerCase();
  return (
    doc.title.toLowerCase().includes(needle) ||
    (doc.file_name ?? '').toLowerCase().includes(needle) ||
    doc.folder_path.toLowerCase().includes(needle)
  );
}

/** True when this subtree contains anything matching the filter. */
function subtreeMatches(node: FolderNode, filter: string): boolean {
  if (!filter) return true;
  if (node.path.toLowerCase().includes(filter.toLowerCase())) return true;
  if (node.documents.some((d) => matches(d, filter))) return true;
  return node.children.some((child) => subtreeMatches(child, filter));
}

function FolderRow({
  node,
  depth,
  expanded,
  selection,
  filter,
  onToggle,
  onSelect,
}: {
  node: FolderNode;
  depth: number;
  expanded: Set<string>;
  selection: Selection;
  filter: string;
  onToggle: (path: string) => void;
  onSelect: (selection: Selection) => void;
}) {
  // A filter auto-reveals matches, otherwise honour the expand/collapse state
  const isOpen = filter ? true : expanded.has(node.path);
  const isSelected = selection?.kind === 'folder' && selection.path === node.path;
  const visibleDocs = filter ? node.documents.filter((d) => matches(d, filter)) : node.documents;
  const visibleChildren = node.children.filter((c) => subtreeMatches(c, filter));
  const hasChildren = node.children.length > 0 || node.documents.length > 0;

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => {
          onSelect({ kind: 'folder', path: node.path });
          if (hasChildren && !filter) onToggle(node.path);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect({ kind: 'folder', path: node.path });
          }
        }}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        className={`flex items-center gap-1.5 py-1.5 pr-2 rounded-md cursor-pointer select-none text-sm transition-colors ${
          isSelected ? 'bg-primary-50 text-primary-800 font-semibold' : 'hover:bg-gray-100 text-gray-700'
        }`}
      >
        <span className="w-4 shrink-0 text-gray-400">
          {hasChildren ? (
            isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : null}
        </span>
        {isOpen ? (
          <FolderOpen size={15} className="shrink-0 text-primary-600" />
        ) : (
          <Folder size={15} className="shrink-0 text-primary-600" />
        )}
        <span className={`truncate ${node.pending ? 'italic text-gray-500' : ''}`}>
          {node.path === '/' ? 'Knowledge Base' : node.name}
        </span>
        {node.totalCount > 0 && (
          <span className="ml-auto text-xs text-gray-400 font-normal tabular-nums">
            {node.totalCount}
          </span>
        )}
        {node.pending && node.totalCount === 0 && (
          <span className="ml-auto text-[10px] uppercase tracking-wide text-gray-400">
            empty
          </span>
        )}
      </div>

      {isOpen && (
        <div>
          {visibleChildren.map((child) => (
            <FolderRow
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              selection={selection}
              filter={filter}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
          {visibleDocs.map((doc) => {
            const isDocSelected = selection?.kind === 'document' && selection.id === doc.id;
            const unembedded = doc.chunk_count === 0 || doc.embedded_chunk_count < doc.chunk_count;
            return (
              <div
                key={doc.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelect({ kind: 'document', id: doc.id })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect({ kind: 'document', id: doc.id });
                  }
                }}
                style={{ paddingLeft: `${(depth + 1) * 14 + 22}px` }}
                className={`flex items-center gap-2 py-1.5 pr-2 rounded-md cursor-pointer select-none text-sm transition-colors ${
                  isDocSelected
                    ? 'bg-primary-100 text-primary-900 font-medium'
                    : 'hover:bg-gray-100 text-gray-600'
                }`}
              >
                <span className="shrink-0">{formatIcon(doc.source_format)}</span>
                <span className="truncate">{doc.title}</span>
                {unembedded && (
                  <AlertTriangle
                    size={13}
                    className="shrink-0 text-amber-500"
                  />
                )}
                <span className="ml-auto text-xs text-gray-400 font-normal tabular-nums shrink-0">
                  {doc.chunk_count}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TreeView({
  root,
  expanded,
  selection,
  filter,
  onToggle,
  onSelect,
}: {
  root: FolderNode;
  expanded: Set<string>;
  selection: Selection;
  filter: string;
  onToggle: (path: string) => void;
  onSelect: (selection: Selection) => void;
}) {
  return (
    <div className="py-1">
      <FolderRow
        node={root}
        depth={0}
        expanded={expanded}
        selection={selection}
        filter={filter}
        onToggle={onToggle}
        onSelect={onSelect}
      />
    </div>
  );
}
