import { AlertTriangle, Check, ChevronsUpDown, Database, Plus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { KnowledgeBase } from '../api';

/**
 * Which knowledge base every other page is acting on.
 *
 * It sits above the navigation rather than inside a settings screen because it
 * changes what "Documents", "Search" and "Dashboard" mean — a selector that
 * quietly redefines the rest of the app should be visible from the rest of the
 * app.
 */
export function KbSwitcher({
  knowledgeBases,
  activeSlug,
  onSwitch,
}: {
  knowledgeBases: KnowledgeBase[];
  activeSlug: string | null;
  onSwitch: (slug: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const active =
    knowledgeBases.find((kb) => kb.slug === activeSlug) ??
    knowledgeBases.find((kb) => kb.is_default) ??
    knowledgeBases[0];

  // With one knowledge base there is nothing to switch between, so the control
  // would be noise. The link to manage them lives in the nav either way.
  if (knowledgeBases.length <= 1) return null;

  return (
    <div className="relative px-4 pt-4" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 transition-colors text-left"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Database size={15} className="text-gray-400 shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-gray-900 truncate">
            {active?.name ?? 'Select…'}
          </span>
          <span className="block text-[11px] text-gray-500 font-mono truncate">
            {active?.embedding_model}
          </span>
        </span>
        <ChevronsUpDown size={14} className="text-gray-400 shrink-0" />
      </button>

      {open && (
        <div
          className="absolute left-4 right-4 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-30 overflow-hidden"
          role="listbox"
        >
          {knowledgeBases.map((kb) => (
            <button
              key={kb.id}
              role="option"
              aria-selected={kb.slug === active?.slug}
              disabled={!kb.is_active}
              onClick={() => {
                setOpen(false);
                if (kb.slug !== active?.slug) onSwitch(kb.slug);
              }}
              className="w-full flex items-start gap-2 px-3 py-2 hover:bg-gray-50 text-left disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="w-4 shrink-0 pt-0.5">
                {kb.slug === active?.slug && <Check size={14} className="text-primary-600" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-gray-900 truncate">{kb.name}</span>
                <span className="block text-[11px] text-gray-500 font-mono truncate">
                  {kb.embedding_model} · {kb.embedding_dimensions}d
                </span>
              </span>
              {kb.last_error && (
                <AlertTriangle size={13} className="text-red-500 shrink-0 mt-0.5" />
              )}
            </button>
          ))}

          <Link
            to="/knowledge-bases"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 border-t border-gray-100 text-sm text-gray-600 hover:bg-gray-50"
          >
            <span className="w-4 shrink-0">
              <Plus size={14} />
            </span>
            Manage knowledge bases
          </Link>
        </div>
      )}
    </div>
  );
}
