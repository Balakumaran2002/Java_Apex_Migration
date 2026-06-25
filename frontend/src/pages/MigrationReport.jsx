import React, { useState, useEffect } from 'react';
import { FileText, Download, CheckCircle, ShieldAlert, Cpu } from 'lucide-react';
import { getMigrationReportUrl } from '../api';

export default function MigrationReport() {
  const [migration, setMigration] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    const lastMigration = JSON.parse(localStorage.getItem('last_migration') || 'null');
    const lastAnalysis = JSON.parse(localStorage.getItem('last_analysis') || 'null');
    setMigration(lastMigration);
    setAnalysis(lastAnalysis);
  }, []);

  if (!migration) {
    return (
      <div className="p-8 text-center glass-card animate-fadeIn">
        <FileText size={48} className="mx-auto text-slate-300 dark:text-slate-700 mb-4" />
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200 mb-2">No Migration Report Available</h3>
        <p className="text-sm text-slate-400 max-w-sm mx-auto mb-6">
          You haven't executed any migrations yet. Run analysis and migration in the Migration Center first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-6 glass-card bg-gradient-to-r from-slate-100 to-indigo-50/20 dark:from-dark-900 dark:to-dark-950/40">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <FileText className="text-indigo-500" size={22} />
            Java Migration Summary Report
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Historical compile diagnostics and rewrite logs.
          </p>
        </div>
        <a
          href={getMigrationReportUrl()}
          className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
        >
          <Download size={14} /> Download PDF
        </a>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column details */}
        <div className="lg:col-span-1 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4">Metadata</h3>
            <table className="w-full text-xs text-left">
              <tbody>
                <tr className="border-b border-slate-100 dark:border-dark-800">
                  <td className="py-3 font-semibold text-slate-400">Target Upgrade</td>
                  <td className="py-3 font-bold text-indigo-600 dark:text-indigo-400">Java {migration.targetVersion}</td>
                </tr>
                <tr className="border-b border-slate-100 dark:border-dark-800">
                  <td className="py-3 font-semibold text-slate-400">Build System</td>
                  <td className="py-3 font-bold text-slate-800 dark:text-slate-200">
                    {analysis ? analysis.projectType : 'Java'}
                  </td>
                </tr>
                <tr className="border-b border-slate-100 dark:border-dark-800">
                  <td className="py-3 font-semibold text-slate-400">Build Status</td>
                  <td className={`py-3 font-bold ${
                    migration.buildStatus === 'Build Success' ? 'text-emerald-500' : 'text-rose-500'
                  }`}>{migration.buildStatus}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="p-6 glass-card">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Updated File Inventory ({migration.modifiedFiles.length})</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {migration.modifiedFiles.length > 0 ? (
                migration.modifiedFiles.map((file, idx) => (
                  <div key={idx} className="text-xs font-mono truncate text-slate-600 dark:text-slate-400">
                    📄 {file}
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No files changed</div>
              )}
            </div>
          </div>
        </div>

        {/* Right column logs */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4">Refactoring Logs</h3>
            <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto max-h-96 leading-relaxed">
              {migration.migrationSummary || 'No details available.'}
            </pre>
          </div>

          {migration.buildErrors && (
            <div className="p-6 glass-card border-rose-500/20">
              <h3 className="text-md font-bold text-rose-500 mb-4 flex items-center gap-2">
                <ShieldAlert size={18} /> Compilation Failures
              </h3>
              <pre className="p-4 rounded-xl bg-rose-950/20 text-rose-300 border border-rose-500/10 text-xs font-mono overflow-x-auto max-h-80 leading-relaxed">
                {migration.buildErrors}
              </pre>
            </div>
          )}

          {migration.suggestedFixes && (
            <div className="p-6 glass-card">
              <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                <Cpu className="text-indigo-500" size={18} />
                AI Compile Recommendations
              </h3>
              <div className="text-sm text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-dark-950/20 p-5 rounded-2xl border border-slate-200/30 dark:border-dark-900/30 whitespace-pre-wrap leading-relaxed">
                {migration.suggestedFixes}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
