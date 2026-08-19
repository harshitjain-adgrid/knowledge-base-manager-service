import { useState } from 'react';
import { FilePlus2, UploadCloud, AlertTriangle } from 'lucide-react';
import { api, normalizeFolder } from '../api';
import type { SupportedFormats } from '../api';
import {
  Button,
  ErrorBanner,
  Field,
  Modal,
  inputClass,
  monoInputClass,
} from './ui';

function parseMetadata(raw: string): Record<string, unknown> | null {
  if (!raw.trim()) return null;
  const parsed = JSON.parse(raw);
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('Metadata must be a JSON object, e.g. {"team": "payments"}');
  }
  return parsed as Record<string, unknown>;
}

export function UploadModal({
  isOpen,
  folder,
  formats,
  onClose,
  onDone,
}: {
  isOpen: boolean;
  folder: string;
  formats: SupportedFormats | null;
  onClose: () => void;
  onDone: (folder: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');

  const extension = file ? `.${file.name.split('.').pop()?.toLowerCase()}` : '';
  const isTabular = formats?.tabular_formats.some((f) => extension === `.${f}`) ?? false;

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const raw = (form.get('metadata') as string) || '';
      const metadata = parseMetadata(raw);
      const destination = normalizeFolder(form.get('folder_path') as string);

      const payload = new FormData();
      payload.append('file', form.get('file') as File);
      payload.append('title', form.get('title') as string);
      payload.append('folder_path', destination);
      if (metadata) payload.append('metadata', JSON.stringify(metadata));

      await api.uploadDocument(payload);
      onDone(destination);
      setFile(null);
      setTitle('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Upload document" isOpen={isOpen} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBanner message={error} />

        <Field label="File" hint={formats ? `Accepted: ${formats.extensions.join(' ')} — max ${formats.max_upload_size_mb}MB` : undefined}>
          <input
            name="file"
            type="file"
            required
            accept={formats?.extensions.join(',')}
            onChange={(e) => {
              const picked = e.target.files?.[0] ?? null;
              setFile(picked);
              // Offer the filename (minus extension) as a starting title
              if (picked && !title) {
                setTitle(picked.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' '));
              }
            }}
            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
          />
        </Field>

        {isTabular && (
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-100 rounded-lg text-sm text-amber-800">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <span>
              Spreadsheets are stored one row per chunk. That works for reference tables
              like fee slabs. Data you would normally filter with a query — and anything
              containing merchant records — does not belong in the knowledge base.
            </span>
          </div>
        )}

        <Field label="Title">
          <input
            name="title"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            placeholder="e.g. Refund Policy"
          />
        </Field>

        <Field label="Folder" hint="Created automatically if it does not exist yet.">
          <input name="folder_path" defaultValue={folder} className={monoInputClass} />
        </Field>

        <Field label="Metadata (optional JSON)">
          <input name="metadata" className={monoInputClass} placeholder='{"team": "payments"}' />
        </Field>

        <div className="pt-2 flex justify-end gap-3">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={busy} icon={<UploadCloud size={16} />}>
            {busy ? 'Processing…' : 'Upload & embed'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function AddTextModal({
  isOpen,
  folder,
  docTypes,
  onClose,
  onDone,
}: {
  isOpen: boolean;
  folder: string;
  docTypes: string[];
  onClose: () => void;
  onDone: (folder: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const metadata = parseMetadata((form.get('metadata') as string) || '');
      const destination = normalizeFolder(form.get('folder_path') as string);
      await api.createDocument({
        title: form.get('title') as string,
        content: form.get('content') as string,
        doc_type: form.get('doc_type') as string,
        folder_path: destination,
        metadata,
      });
      onDone(destination);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Add document" isOpen={isOpen} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBanner message={error} />

        <div className="grid grid-cols-2 gap-4">
          <Field label="Title">
            <input name="title" required className={inputClass} placeholder="Document title" />
          </Field>
          <Field label="Type" hint="api_definition chunks per endpoint; anything else as prose.">
            <select name="doc_type" className={`${inputClass} bg-white`} defaultValue={docTypes[0]}>
              {docTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Folder" hint="Created automatically if it does not exist yet.">
          <input name="folder_path" defaultValue={folder} className={monoInputClass} />
        </Field>

        <Field label="Content">
          <textarea
            name="content"
            required
            rows={12}
            className={`${monoInputClass} resize-y`}
            placeholder="Paste the knowledge here…"
          />
        </Field>

        <Field label="Metadata (optional JSON)">
          <input name="metadata" className={monoInputClass} placeholder='{"status": "draft"}' />
        </Field>

        <div className="pt-2 flex justify-end gap-3">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={busy} icon={<FilePlus2 size={16} />}>
            {busy ? 'Embedding…' : 'Save & embed'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function NewFolderModal({
  isOpen,
  parent,
  onClose,
  onCreate,
}: {
  isOpen: boolean;
  parent: string;
  onClose: () => void;
  onCreate: (path: string) => void;
}) {
  const [name, setName] = useState('');

  return (
    <Modal title="New folder" isOpen={isOpen} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          onCreate(normalizeFolder(`${parent}/${name}`));
          setName('');
        }}
        className="space-y-4"
      >
        <Field label="Parent">
          <input value={parent} readOnly className={`${monoInputClass} bg-gray-50 text-gray-500`} />
        </Field>
        <Field
          label="Folder name"
          hint="Folders are derived from document paths, so this one is only kept in the browser until you put a document in it."
        >
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={monoInputClass}
            placeholder="policies"
          />
        </Field>
        <div className="pt-2 flex justify-end gap-3">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary">Create</Button>
        </div>
      </form>
    </Modal>
  );
}
