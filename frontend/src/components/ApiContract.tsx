import { AlertTriangle, Globe, KeyRound, MessageSquare, Repeat } from 'lucide-react';
import { Badge } from './ui';

/**
 * An API card rendered as the contract it is.
 *
 * A card's front matter is stripped out of the document body at ingest and kept
 * as metadata, which is right — it is structured data, not prose, and the body
 * is what gets embedded. But it left the admin UI showing two paragraphs of
 * description for a document that actually defines an endpoint, its fields,
 * their prompts and its error messages. Everything was stored; none of it was
 * legible.
 *
 * This is that data, read back the way someone reviewing a card needs to see it.
 */

export interface ApiCardMetadata {
  api_id?: string;
  base_url?: string;
  body_root?: string;
  constants?: Record<string, unknown>;
  domain?: string;
  method?: string;
  path?: string;
  mpin_required?: boolean;
  idempotent?: boolean;
  version?: number | string;
  last_verified?: string;
  status?: string;
  fields?: Array<Record<string, unknown>>;
  returns?: { success?: string[]; errors?: Record<string, string> };
  utterances?: string[];
}

/** Whether a document is an API card at all. */
export function isApiCard(metadata: Record<string, unknown> | null | undefined): boolean {
  return Boolean(metadata && typeof metadata === 'object' && 'api_id' in metadata);
}

const methodTone: Record<string, 'blue' | 'green' | 'amber' | 'red' | 'gray'> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'amber',
  PATCH: 'amber',
  DELETE: 'red',
};

function Section({ title, count, children }: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        {title}
        {count !== undefined && <span className="ml-1.5 text-gray-400">({count})</span>}
      </h4>
      {children}
    </div>
  );
}

export function ApiContract({ metadata }: { metadata: ApiCardMetadata }) {
  const fields = Array.isArray(metadata.fields) ? metadata.fields : [];
  const required = fields.filter((f) => f.required);
  const optional = fields.filter((f) => !f.required);
  const utterances = Array.isArray(metadata.utterances) ? metadata.utterances : [];
  const errors = metadata.returns?.errors ?? {};

  return (
    <div className="space-y-6">
      {/* The call itself */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge tone={methodTone[String(metadata.method).toUpperCase()] ?? 'gray'}>
          {String(metadata.method ?? '?').toUpperCase()}
        </Badge>
        <code className="font-mono text-sm text-gray-900 break-all">
          {metadata.base_url && (
            <span className="text-gray-400">{String(metadata.base_url).replace(/\/$/, '')}</span>
          )}
          {metadata.path}
        </code>
      </div>

      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="font-mono text-gray-500">{metadata.api_id}</span>
        {metadata.domain && <Badge tone="gray">{metadata.domain}</Badge>}
        {metadata.mpin_required && (
          <Badge tone="amber">
            <KeyRound size={11} className="mr-1" /> MPIN required
          </Badge>
        )}
        {metadata.idempotent && (
          <Badge tone="gray">
            <Repeat size={11} className="mr-1" /> safe to retry
          </Badge>
        )}
        {metadata.status === 'example' && (
          <Badge tone="red">
            <AlertTriangle size={11} className="mr-1" /> synthetic seed — not a real contract
          </Badge>
        )}
        {metadata.status === 'live' && (
          <Badge tone="green">
            <Globe size={11} className="mr-1" /> real public API — callable
          </Badge>
        )}
      </div>

      {/* Values that are always sent, whatever the merchant said. Without these
          the path alone does not identify the action — two APIs can share one
          endpoint and differ only by a discriminator. */}
      {metadata.constants && Object.keys(metadata.constants).length > 0 && (
        <Section title="Always sent">
          <div className="space-y-1">
            {Object.entries(metadata.constants).map(([key, value]) => (
              <div key={key} className="flex gap-2 text-sm">
                <code className="font-mono text-xs text-gray-500 shrink-0">{key}</code>
                <span className="text-gray-400">=</span>
                <code className="font-mono text-xs text-primary-700 break-all">
                  {String(value)}
                </code>
              </div>
            ))}
          </div>
          {metadata.body_root && (
            <p className="text-xs text-gray-500 mt-2">
              Collected fields nest under{' '}
              <code className="font-mono">{String(metadata.body_root)}</code> in the body.
            </p>
          )}
        </Section>
      )}

      {/* Fields: what has to be collected before the call can be made */}
      {fields.length > 0 && (
        <Section title="Request fields" count={fields.length}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase tracking-wider">
                  <th className="text-left font-medium pb-2 pr-4">Field</th>
                  <th className="text-left font-medium pb-2 pr-4">Type</th>
                  <th className="text-left font-medium pb-2">What the assistant asks</th>
                </tr>
              </thead>
              <tbody>
                {[...required, ...optional].map((field, index) => (
                  <tr key={index} className="border-t border-gray-100 align-top">
                    <td className="py-2 pr-4 whitespace-nowrap">
                      <code className="font-mono text-xs text-gray-900">
                        {String(field.name)}
                      </code>
                      {field.required ? (
                        <span className="ml-1.5 text-xs text-red-600" title="required">*</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-4 text-xs text-gray-600 whitespace-nowrap">
                      {String(field.type ?? '—')}
                      {field.in ? (
                        <div className="text-gray-400">in {String(field.in)}</div>
                      ) : null}
                      {Array.isArray(field.values) && (
                        <div className="text-gray-400 font-mono">
                          {(field.values as string[]).join(' | ')}
                        </div>
                      )}
                      {field.default !== undefined && (
                        <div className="text-gray-400">default {String(field.default)}</div>
                      )}
                    </td>
                    <td className="py-2 text-gray-700">
                      {field.prompt ? (
                        <span className="italic">“{String(field.prompt)}”</span>
                      ) : field.required ? (
                        <span className="text-red-600 text-xs">
                          required but has no prompt — nothing to ask the merchant
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                      {field.example !== undefined && (
                        <div className="text-xs text-gray-400 mt-0.5">
                          e.g. {String(field.example)}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            <span className="text-red-600">*</span> required — the assistant collects these
            before calling, using the prompt shown.
          </p>
        </Section>
      )}

      {/* What comes back */}
      {(metadata.returns?.success?.length || Object.keys(errors).length > 0) && (
        <Section title="Returns">
          {metadata.returns?.success?.length ? (
            <p className="text-sm text-gray-700 mb-2">
              <span className="text-gray-500">On success: </span>
              <code className="font-mono text-xs">
                {metadata.returns.success.join(', ')}
              </code>
            </p>
          ) : null}
          {Object.entries(errors).map(([code, message]) => (
            <div key={code} className="flex gap-2 text-sm py-0.5">
              <code className="font-mono text-xs text-red-700 shrink-0 w-8">{code}</code>
              <span className="text-gray-700">{message}</span>
            </div>
          ))}
        </Section>
      )}

      {/* The phrases retrieval actually matches on */}
      {utterances.length > 0 && (
        <Section title="Example utterances" count={utterances.length}>
          <div className="flex flex-wrap gap-1.5">
            {utterances.map((utterance, index) => (
              <span
                key={index}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-50 border border-gray-200 text-xs text-gray-700"
              >
                <MessageSquare size={11} className="text-gray-400 shrink-0" />
                {utterance}
              </span>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Each of these is indexed on its own. A merchant's phrasing is matched against
            these before it is matched against the description.
          </p>
        </Section>
      )}

      {(metadata.version !== undefined || metadata.last_verified) && (
        <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
          {metadata.version !== undefined && <>version {String(metadata.version)}</>}
          {metadata.version !== undefined && metadata.last_verified && ' · '}
          {metadata.last_verified && <>last verified {String(metadata.last_verified)}</>}
        </p>
      )}
    </div>
  );
}
