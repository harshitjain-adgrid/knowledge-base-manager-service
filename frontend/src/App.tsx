import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Search,
  Settings as SettingsIcon,
  FolderOpen,
  Library,
  LogOut,
  Database,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import type { KnowledgeBase } from './api';
import { api, getActiveKb, getToken, setActiveKb, setUnauthorizedHandler } from './api';
import { Dashboard } from './pages/Dashboard';
import { Documents } from './pages/Documents';
import { KnowledgeBases } from './pages/KnowledgeBases';
import { SearchSimulator } from './pages/SearchSimulator';
import { Settings } from './pages/Settings';
import { Login } from './pages/Login';
import { KbSwitcher } from './components/KbSwitcher';
import { Spinner } from './components/ui';

function Sidebar({
  username,
  onSignOut,
  knowledgeBases,
  activeKb,
  onSwitchKb,
}: {
  username: string | null;
  onSignOut: () => void;
  knowledgeBases: KnowledgeBase[];
  activeKb: string | null;
  onSwitchKb: (slug: string) => void;
}) {
  const location = useLocation();
  const [folders, setFolders] = useState<string[]>([]);

  useEffect(() => {
    // Refresh on navigation so a newly created folder appears without a reload.
    // Keyed on the knowledge base too: the folder list belongs to it, and
    // showing the previous one's folders after a switch would be a lie.
    api
      .tree()
      .then((tree) => setFolders(tree.folders.filter((f) => f.document_count > 0).map((f) => f.path)))
      .catch(() => setFolders([]));
  }, [location.pathname, activeKb]);

  const navItem = (to: string, active: boolean, icon: React.ReactNode, label: string) => (
    <Link to={to} className={`nav-item ${active ? 'active' : ''}`}>
      {icon} {label}
    </Link>
  );

  return (
    <div className="w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col shrink-0">
      <div className="p-6 flex items-center gap-3 border-b border-gray-100">
        <div className="bg-primary-100 p-2 rounded-lg text-primary-700">
          <Library size={26} strokeWidth={2.5} />
        </div>
        <div className="min-w-0">
          <h1 className="font-bold text-lg text-gray-900 tracking-tight truncate">
            Chotu Knowledge Hub
          </h1>
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
            Admin
          </p>
        </div>
      </div>

      <KbSwitcher
        knowledgeBases={knowledgeBases}
        activeSlug={activeKb}
        onSwitch={onSwitchKb}
      />

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="space-y-1 mb-8">
          {navItem('/', location.pathname === '/', <LayoutDashboard size={20} />, 'Dashboard')}
          {navItem('/documents', location.pathname.startsWith('/documents'), <FileText size={20} />, 'All Documents')}
          {navItem('/search', location.pathname === '/search', <Search size={20} />, 'Search Simulator')}
          {navItem(
            '/knowledge-bases',
            location.pathname === '/knowledge-bases',
            <Database size={20} />,
            'Knowledge Bases',
          )}
        </div>

        {folders.length > 0 && (
          <>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-4">
              Folders
            </h3>
            <div className="space-y-1">
              {folders.map((folder) => (
                <Link
                  key={folder}
                  to={`/documents?folder=${encodeURIComponent(folder)}`}
                  className="nav-item !py-2 text-sm"
                >
                  <FolderOpen size={16} className="text-gray-400 shrink-0" />
                  <span className="truncate font-mono text-xs">{folder}</span>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="p-4 border-t border-gray-100 space-y-1">
        {navItem('/settings', location.pathname === '/settings', <SettingsIcon size={18} />, 'Settings')}
        {username && (
          <button onClick={onSignOut} className="nav-item text-sm w-full">
            <LogOut size={18} />
            <span className="truncate">Sign out ({username})</span>
          </button>
        )}
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900">Page not found</h1>
      <p className="text-gray-500 mt-2">
        <Link to="/" className="text-primary-700 hover:underline font-medium">
          Back to the dashboard
        </Link>
      </p>
    </div>
  );
}

export default function App() {
  // null = still checking, false = no sign-in required, string = signed in
  const [username, setUsername] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState<boolean | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [activeKb, setActive] = useState<string | null>(getActiveKb());

  const check = useCallback(async () => {
    try {
      const me = await api.me();
      setAuthRequired(!me.authenticated);
      setUsername(me.username);
    } catch {
      // /auth/me is public, so a failure here means the server is unreachable
      // rather than that we are signed out. Assume sign-in is needed only if a
      // token was present and rejected.
      setAuthRequired(Boolean(getToken()));
      setUsername(null);
    }
  }, []);

  const loadKnowledgeBases = useCallback(async () => {
    try {
      const list = await api.knowledgeBases();
      setKnowledgeBases(list.knowledge_bases);

      // A stored selection can outlive the knowledge base it names — someone
      // removed it, or this browser has a slug from a different deployment.
      // Left alone it would 404 every request, so fall back to the default.
      const stored = getActiveKb();
      const known = list.knowledge_bases.some((kb) => kb.slug === stored && kb.is_active);
      if (stored && !known) {
        setActiveKb(null);
        setActive(null);
      }
    } catch {
      setKnowledgeBases([]);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthRequired(true);
      setUsername(null);
    });
    check();
  }, [check]);

  useEffect(() => {
    if (authRequired === false) loadKnowledgeBases();
  }, [authRequired, loadKnowledgeBases]);

  const switchKb = (slug: string) => {
    setActiveKb(slug);
    setActive(slug);
  };

  const signOut = async () => {
    await api.logout();
    setAuthRequired(true);
    setUsername(null);
  };

  if (authRequired === null) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 gap-2">
        <Spinner /> Loading…
      </div>
    );
  }

  if (authRequired) {
    return (
      <Login
        onSignedIn={(name) => {
          setUsername(name);
          setAuthRequired(false);
        }}
      />
    );
  }

  return (
    <Router>
      <div className="flex min-h-screen bg-gray-50/50">
        <Sidebar
          username={username}
          onSignOut={signOut}
          knowledgeBases={knowledgeBases}
          activeKb={activeKb}
          onSwitchKb={switchKb}
        />
        <main className="flex-1 min-w-0 overflow-x-hidden">
          {/* Keyed on the knowledge base so switching remounts the page rather
              than leaving the previous one's documents on screen. */}
          <Routes key={activeKb ?? 'default'}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/search" element={<SearchSimulator />} />
            <Route
              path="/knowledge-bases"
              element={
                <KnowledgeBases
                  knowledgeBases={knowledgeBases}
                  reload={loadKnowledgeBases}
                  activeKb={activeKb}
                  onSwitch={switchKb}
                />
              }
            />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
