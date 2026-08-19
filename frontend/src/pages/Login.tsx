import { useState } from 'react';
import { Library, LogIn } from 'lucide-react';
import { api } from '../api';
import { Button, ErrorBanner, Field, inputClass } from '../components/ui';

export function Login({ onSignedIn }: { onSignedIn: (username: string) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(username.trim(), password);
      onSignedIn(result.username);
    } catch (err: any) {
      setError(err.message);
      setPassword('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="bg-primary-100 p-2.5 rounded-lg text-primary-700">
            <Library size={28} strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-bold text-xl text-gray-900 tracking-tight">
              Chotu Knowledge Hub
            </h1>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
              Admin
            </p>
          </div>
        </div>

        <form onSubmit={submit} className="glass-panel p-6 space-y-4">
          <ErrorBanner message={error} />

          <Field label="Username">
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
              required
            />
          </Field>

          <Field label="Password">
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              required
            />
          </Field>

          <Button
            type="submit"
            variant="primary"
            loading={busy}
            icon={<LogIn size={16} />}
            className="w-full justify-center"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="text-xs text-gray-400 text-center mt-6">
          Accounts are created with{' '}
          <span className="font-mono">python -m app.admin_cli create &lt;username&gt;</span>
        </p>
      </div>
    </div>
  );
}
