import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect } from 'react';

export function Modal({
  title,
  isOpen,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className={`bg-white rounded-xl shadow-xl w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} overflow-hidden flex flex-col max-h-[90vh]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-100 whitespace-pre-wrap">
      {message}
    </div>
  );
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block animate-spin rounded-full h-4 w-4 border-2 border-current/20 border-t-current ${className}`}
    />
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-500 mt-1">{hint}</p>}
    </div>
  );
}

export const inputClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 outline-none';

export const monoInputClass = `${inputClass} font-mono text-sm`;

export function Badge({
  children,
  tone = 'blue',
}: {
  children: ReactNode;
  tone?: 'blue' | 'gray' | 'green' | 'red' | 'amber';
}) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    gray: 'bg-gray-50 text-gray-600 border-gray-200',
    green: 'bg-green-50 text-green-700 border-green-100',
    red: 'bg-red-50 text-red-700 border-red-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="p-12 text-center">
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-gray-100 mb-4 text-gray-400">
        {icon}
      </div>
      <h3 className="text-base font-medium text-gray-900 mb-1">{title}</h3>
      <div className="text-sm text-gray-500 max-w-sm mx-auto">{children}</div>
    </div>
  );
}

export function Button({
  variant = 'secondary',
  loading = false,
  icon,
  children,
  className = '',
  ...props
}: {
  variant?: 'primary' | 'secondary' | 'danger';
  loading?: boolean;
  icon?: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants = {
    primary: 'bg-primary-600 text-white hover:bg-primary-700 shadow-sm',
    secondary: 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 shadow-sm',
    danger: 'bg-red-50 border border-red-100 text-red-700 hover:bg-red-100',
  };
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}
