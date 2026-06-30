import React, { useMemo, useState } from 'react';
import { Clock, FileText, ExternalLink, Trash2, ChevronRight, CalendarDays, GitBranch, Server, MonitorDot, Database, Package, Wrench, AlertTriangle } from 'lucide-react';
import { clearMigrationHistory } from '../api';

const fieldLabelMap = {
  repository_name: 'Repository Name',
  repository_url: 'Repository URL',
  branch_name: 'Branch',
  start_time: 'Migration Start Time',
  end_time: 'Migration End Time',
  target_version: 'Target Java Version',
  migration_status: 'Migration Status',
  build_status: 'Build Status',
  runtime_status: 'Runtime Status',
  files_changed_java: 'Java Files Modified',
  files_changed_xml: 'XML Files Modified',
  files_changed_config: 'Config Files Modified',
  files_changed_total: 'Total Files Modified',
  error_message: 'Errors',
  execution_time: 'Execution Time',
};

const formatValue = (value) => {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : 'None';
  }
  if (value === null || value === undefined || value === '') {
    return 'Unknown';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
};

const getStatusTone = (value) => {
  const normalized = String(value || '').toLowerCase();
  if (normalized.includes('success') || normalized.includes('running') || normalized.includes('complete')) {
    return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
  }
  if (normalized.includes('warning') || normalized.includes('partial') || normalized.includes('detected')) {
    return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
  }
  if (normalized.includes('fail') || normalized.includes('error') || normalized.includes('missing')) {
    return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20';
  }
  return 'bg-slate-500/10 text-slate-600 dark:text-slate-300 border-slate-500/20';
};

export default function MigrationHistory({ history, setHistory, setActiveTab }) {
  const [selectedId, setSelectedId] = useState(history?.[0]?.id || null);

  const selectedEntry = useMemo(() => {
    return history?.find((item) => item.id === selectedId) || history?.[0] || null;
  }, [history, selectedId]);

  const clearHistory = async () => {
    try {
      await clearMigrationHistory();
      setHistory([]);
      setSelectedId(null);
    } catch (e) {
      console.error("Failed to clear history", e);
    }
  };

  if (!history || history.length === 0) {
    return (
      <div className="p-8 glass-card text-center">
        <Clock size={44} className="mx-auto text-slate-300 dark:text-slate-700 mb-4" />
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200 mb-2">No Migration History</h3>
        <p className="text-sm text-slate-500 max-w-lg mx-auto mb-6">
          Run a migration first, and this page will track the repository, build, runtime, frontend, and UI validation details.
        </p>
        <button
          onClick={() => setActiveTab('migration')}
          className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold text-sm transition-all"
        >
          Open Migration Center
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="p-6 glass-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <Clock className="text-brand-500" size={22} />
            Migration History
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Click a migration to reopen its full report and validation summary.
          </p>
        </div>
        <button
          onClick={clearHistory}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-rose-500/20 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 text-xs font-semibold transition-colors"
        >
          <Trash2 size={14} /> Clear History
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-1 space-y-3">
          {history.map((entry) => (
            <button
              key={entry.id}
              onClick={() => setSelectedId(entry.id)}
              className={`w-full text-left p-4 rounded-2xl border transition-all ${
                selectedEntry?.id === entry.id
                  ? 'bg-brand-500/10 border-brand-500/30 shadow-lg shadow-brand-500/10'
                  : 'bg-white/50 dark:bg-dark-950/40 border-slate-200/60 dark:border-dark-800/60 hover:border-brand-500/20'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white truncate max-w-[240px]">
                    {entry.repository_name || entry.repoName || 'Repository'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                    <CalendarDays size={12} /> {entry.start_time ? new Date(entry.start_time).toLocaleString() : 'Unknown'}
                  </div>
                </div>
                <ChevronRight size={16} className="text-slate-400" />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className={`px-2 py-1 rounded-md text-[10px] font-bold border ${getStatusTone(entry.migration_status)}`}>
                  {entry.migration_status || 'Unknown'}
                </span>
                <span className={`px-2 py-1 rounded-md text-[10px] font-bold border ${getStatusTone(entry.build_status)}`}>
                  {entry.build_status || 'Unknown'}
                </span>
              </div>
            </button>
          ))}
        </div>

        <div className="xl:col-span-2 space-y-6">
          {selectedEntry && (
            <>
              <div className="p-6 glass-card">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <FileText className="text-indigo-500" size={18} />
                      {selectedEntry.repository_name || selectedEntry.repoName || 'Migration Report'}
                    </h3>
                    <p className="mt-1 text-xs text-slate-400 break-all">
                      {selectedEntry.repository_url || selectedEntry.repoUrl}
                    </p>
                  </div>
                  <button
                    onClick={() => setActiveTab('migrationReport')}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold"
                  >
                    <ExternalLink size={14} /> Open Latest Report
                  </button>
                </div>

                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(fieldLabelMap).map(([key, label]) => (
                    <div key={key} className="p-4 rounded-2xl bg-slate-50/80 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60">
                      <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
                      <div className="mt-1 text-sm font-semibold text-slate-800 dark:text-slate-200 break-words">
                        {formatValue(selectedEntry[key])}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-5 glass-card">
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                    <Server className="text-indigo-500" size={16} />
                    Runtime Snapshot
                  </h4>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">Backend</span>
                      <span className={`px-2 py-1 rounded-md text-[11px] font-bold border ${getStatusTone(selectedEntry.backendStatus)}`}>
                        {formatValue(selectedEntry.backendStatus)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">Frontend</span>
                      <span className={`px-2 py-1 rounded-md text-[11px] font-bold border ${getStatusTone(selectedEntry.frontendStatus)}`}>
                        {formatValue(selectedEntry.frontendStatus)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">UI</span>
                      <span className={`px-2 py-1 rounded-md text-[11px] font-bold border ${getStatusTone(selectedEntry.uiStatus)}`}>
                        {formatValue(selectedEntry.uiStatus)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-5 glass-card">
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                    <Wrench className="text-indigo-500" size={16} />
                    Change Counts
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl bg-slate-50/80 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
                      <div className="text-[11px] uppercase text-slate-400 font-semibold">Files</div>
                      <div className="text-2xl font-extrabold text-slate-900 dark:text-white">{selectedEntry.totalFilesModified ?? 0}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50/80 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
                      <div className="text-[11px] uppercase text-slate-400 font-semibold">Dependencies</div>
                      <div className="text-2xl font-extrabold text-slate-900 dark:text-white">{selectedEntry.dependenciesUpdated ?? 0}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50/80 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
                      <div className="text-[11px] uppercase text-slate-400 font-semibold">Configs</div>
                      <div className="text-2xl font-extrabold text-slate-900 dark:text-white">{selectedEntry.configurationFilesModified ?? 0}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50/80 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
                      <div className="text-[11px] uppercase text-slate-400 font-semibold">Exec Time</div>
                      <div className="text-lg font-extrabold text-slate-900 dark:text-white">{selectedEntry.executionTime || 'Unknown'}</div>
                    </div>
                  </div>
                </div>
              </div>

              {(selectedEntry.warnings || selectedEntry.errorsFixed) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-5 glass-card">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-3">
                      <AlertTriangle className="text-amber-500" size={16} />
                      Warnings
                    </h4>
                    <div className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap">
                      {formatValue(selectedEntry.warnings)}
                    </div>
                  </div>
                  <div className="p-5 glass-card">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-3">
                      <MonitorDot className="text-emerald-500" size={16} />
                      Errors Fixed
                    </h4>
                    <div className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap">
                      {formatValue(selectedEntry.errorsFixed)}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
