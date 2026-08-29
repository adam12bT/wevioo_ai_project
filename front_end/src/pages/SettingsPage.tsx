import { Settings as SettingsIcon, Server, ExternalLink, Info } from 'lucide-react';
import { API } from '@/api/urls';

export function SettingsPage() {
  const workerUrl = API.worker;
  const agentUrl = API.agent;
  const extractorUrl = API.extractor;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Settings</h2>
        <p className="mt-1 text-sm text-slate-500">Configure API endpoints and application behavior.</p>
      </div>

      {/* API Configuration */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 mb-4">
          <Server className="h-5 w-5 text-teal-500" />
          <h3 className="text-sm font-semibold text-slate-800">API Endpoints</h3>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500">Worker API URL</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                readOnly
                value={workerUrl}
                className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 font-mono"
              />
              <a
                href={workerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-slate-300 p-2 text-slate-500 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
            <p className="mt-1 text-xs text-slate-400">Manages jobs, generation, evaluation, versions, and downloads.</p>
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500">Agent API URL</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                readOnly
                value={agentUrl}
                className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 font-mono"
              />
              <a
                href={agentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-slate-300 p-2 text-slate-500 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
            <p className="mt-1 text-xs text-slate-400">Manages the company knowledge base.</p>
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500">Extractor API URL</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                readOnly
                value={extractorUrl || 'Not configured'}
                className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 font-mono"
              />
              {extractorUrl && (
                <a
                  href={`${extractorUrl}/health`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-slate-300 p-2 text-slate-500 hover:bg-slate-50"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
            <p className="mt-1 text-xs text-slate-400">Extracts OCR, tables, layout metadata, and indexes document chunks.</p>
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2.5 rounded-lg bg-blue-50 border border-blue-200 p-3">
          <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-800">
            These URLs are configured via environment variables (<code className="font-mono">VITE_WORKER_API_URL</code>, <code className="font-mono">VITE_AGENT_API_BASE_URL</code>, and <code className="font-mono">VITE_EXTRACTOR_API_URL</code>). Update the <code className="font-mono">.env</code> file and restart the dev server to change them.
          </p>
        </div>
      </div>

      {/* About */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 mb-3">
          <SettingsIcon className="h-5 w-5 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-800">About</h3>
        </div>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Version</dt>
            <dd className="font-medium text-slate-700">1.0.0</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Technology</dt>
            <dd className="font-medium text-slate-700">React 18 + Vite + TypeScript</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Purpose</dt>
            <dd className="font-medium text-slate-700">AI-powered RFP/tender response platform</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
