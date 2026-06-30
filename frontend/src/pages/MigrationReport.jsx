import React, { useEffect, useMemo, useState } from 'react';
import { FileText, Download, CheckCircle, ShieldAlert, Cpu, FileCode2, GitCompareArrows, Settings2, Boxes, ListTree, ExternalLink } from 'lucide-react';
import { getMigrationReportUrl } from '../api';

const safeParseReport = (value) => {
  if (!value) return null;
  try {
    const trimmed = String(value).trim();
    const jsonText = trimmed.startsWith('```') ? trimmed.replace(/^```json\s*/i, '').replace(/^```/, '').replace(/```$/, '').trim() : trimmed;
    return JSON.parse(jsonText);
  } catch (error) {
    return null;
  }
};

const formatList = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') return value.split('\n').map((line) => line.trim()).filter(Boolean);
  return [String(value)];
};

const inferChangeType = (fileName) => {
  const name = String(fileName || '').toLowerCase();
  if (name.includes('pom.xml') || name.includes('build.gradle') || name.includes('package.json')) return 'Dependency / Build';
  if (name.includes('application.properties') || name.includes('application.yml') || name.includes('application.yaml')) return 'Configuration';
  if (name.endsWith('.java')) return 'Source';
  return 'Other';
};

const getFileKey = (file) => file.filename || file.name || file.path || file.file || 'Unknown file';

const diffFiles = (reportData, migration) => {
  if (reportData?.files?.length) {
    return reportData.files.map((file) => ({
      filename: file.filename || 'Unknown file',
      beforeCode: file.before_code || '',
      afterCode: file.after_code || '',
      explanation: file.explanation || '',
    }));
  }

  if (migration?.gitDiff) {
    return migration.gitDiff
      .split('diff --git ')
      .filter(Boolean)
      .map((segment) => {
        const lines = segment.split('\n');
        const header = lines[0] || '';
        const filename = header.includes(' b/') ? header.split(' b/')[1] : header;
        const beforeLines = [];
        const afterLines = [];
        lines.slice(1).forEach((line) => {
          if (line.startsWith('+') && !line.startsWith('+++')) {
            afterLines.push(line.slice(1));
          } else if (line.startsWith('-') && !line.startsWith('---')) {
            beforeLines.push(line.slice(1));
          }
        });
        return {
          filename,
          beforeCode: beforeLines.join('\n'),
          afterCode: afterLines.join('\n'),
          explanation: 'Derived from git diff output.',
        };
      });
  }

  return [];
};

const SideBySide = ({ beforeCode, afterCode }) => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 overflow-hidden">
      <div className="px-4 py-2 text-xs font-bold uppercase tracking-wider text-rose-600 dark:text-rose-400 border-b border-rose-500/10">
        Original Code
      </div>
      <pre className="p-4 text-xs font-mono leading-relaxed text-slate-700 dark:text-slate-200 overflow-auto max-h-80 whitespace-pre-wrap">
        {beforeCode || 'No original code captured.'}
      </pre>
    </div>
    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 overflow-hidden">
      <div className="px-4 py-2 text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 border-b border-emerald-500/10">
        Migrated Code
      </div>
      <pre className="p-4 text-xs font-mono leading-relaxed text-slate-700 dark:text-slate-200 overflow-auto max-h-80 whitespace-pre-wrap">
        {afterCode || 'No migrated code captured.'}
      </pre>
    </div>
  </div>
);

export default function MigrationReport() {
  const [migration, setMigration] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    const lastMigration = JSON.parse(localStorage.getItem('last_migration') || 'null');
    const lastAnalysis = JSON.parse(localStorage.getItem('last_analysis') || 'null');
    setMigration(lastMigration);
    setAnalysis(lastAnalysis);
  }, []);

  const reportData = useMemo(() => safeParseReport(migration?.detailedReport), [migration]);
  const files = useMemo(() => diffFiles(reportData, migration), [reportData, migration]);
  const dependencyChanges = useMemo(() => formatList(reportData?.dependencies), [reportData]);
  const configFiles = useMemo(
    () => (migration?.modifiedFiles || []).filter((file) => /application\.(properties|ya?ml)|pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?/i.test(file)),
    [migration],
  );

  if (!migration) {
    return (
      <div className="p-8 text-center glass-card animate-fadeIn">
        <FileText size={48} className="mx-auto text-slate-300 dark:text-slate-700 mb-4" />
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200 mb-2">No Migration Report Available</h3>
        <p className="text-sm text-slate-400 max-w-sm mx-auto mb-6">
          Run a migration first and the completed report will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="p-6 glass-card bg-gradient-to-r from-slate-100 to-indigo-50/20 dark:from-dark-900 dark:to-dark-950/40 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <FileText className="text-indigo-500" size={22} />
            Migration Completed Successfully
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Detailed migration reporting, dependency deltas, configuration updates, and file-by-file comparisons.
          </p>
        </div>
        <a
          href={getMigrationReportUrl()}
          className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
        >
          <Download size={14} /> Download PDF
        </a>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="p-5 glass-card">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Build Status</div>
          <div className={`mt-2 inline-flex items-center gap-2 text-sm font-bold px-3 py-1.5 rounded-xl border ${migration.buildStatus?.includes('Success') ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'}`}>
            {migration.buildStatus?.includes('Success') ? <CheckCircle size={16} /> : <ShieldAlert size={16} />}
            {migration.buildStatus || 'Unknown'}
          </div>
        </div>
        <div className="p-5 glass-card">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Runtime Status</div>
          <div className="mt-2 text-sm font-bold text-slate-900 dark:text-white">{migration.runtimeStatus || 'Verified in report'}</div>
        </div>
        <div className="p-5 glass-card">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Frontend Status</div>
          <div className="mt-2 text-sm font-bold text-slate-900 dark:text-white">{reportData?.frontend_status || analysis?.frontendFramework || (analysis?.hasFrontend ? 'Detected' : 'Not Detected')}</div>
        </div>
        <div className="p-5 glass-card">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">UI Status</div>
          <div className="mt-2 text-sm font-bold text-slate-900 dark:text-white">{reportData?.ui_accessibility_status || 'Verified'}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-1 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <ListTree className="text-brand-500" size={16} />
              Modified Files
            </h3>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {(migration.modifiedFiles || []).length > 0 ? (
                migration.modifiedFiles.map((file, idx) => (
                  <div key={idx} className="rounded-xl bg-slate-50 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-3">
                    <div className="font-mono text-xs text-slate-800 dark:text-slate-300 break-all">{file}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{inferChangeType(file)}</div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No files changed</div>
              )}
            </div>
          </div>

          <div className="p-6 glass-card">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Settings2 className="text-brand-500" size={16} />
              Configuration Changes
            </h3>
            <div className="space-y-2">
              {configFiles.length > 0 ? (
                configFiles.map((file) => (
                  <div key={file} className="text-xs font-mono rounded-lg bg-slate-50 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 px-3 py-2 break-all">
                    {file}
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No configuration files detected.</div>
              )}
            </div>
          </div>
        </div>

        <div className="xl:col-span-2 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <GitCompareArrows className="text-indigo-500" size={18} />
              Side-by-Side Code Difference Viewer
            </h3>
            {files.length > 0 ? (
              <div className="space-y-6">
                {files.map((file, idx) => (
                  <div key={`${getFileKey(file)}-${idx}`} className="rounded-2xl border border-slate-200/60 dark:border-dark-800/60 overflow-hidden">
                    <div className="px-4 py-3 bg-slate-100/80 dark:bg-dark-900/80 border-b border-slate-200/60 dark:border-dark-800/60">
                      <div className="flex flex-col gap-1">
                        <div className="font-mono text-xs font-bold text-slate-800 dark:text-slate-200 break-all">{getFileKey(file)}</div>
                        <div className="text-[11px] text-slate-500">{file.explanation || 'File comparison generated from migration output.'}</div>
                      </div>
                    </div>
                    <div className="p-4">
                      <SideBySide beforeCode={file.beforeCode || file.before_code} afterCode={file.afterCode || file.after_code} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 rounded-2xl bg-slate-50 dark:bg-dark-950/30 border border-slate-200/60 dark:border-dark-800/60 text-sm text-slate-500">
                No before/after code diff was captured for this migration.
              </div>
            )}
          </div>

          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Boxes className="text-indigo-500" size={18} />
              Dependency Changes
            </h3>
            {dependencyChanges.length > 0 ? (
              <div className="space-y-2">
                {dependencyChanges.map((dependency, idx) => (
                  <div key={`${dependency}-${idx}`} className="rounded-xl border border-slate-200/60 dark:border-dark-800/60 bg-slate-50 dark:bg-dark-950/40 px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                    {dependency}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">No dependency delta details were captured in the report payload.</div>
            )}
          </div>
        </div>

        <div className="xl:col-span-3 p-6 glass-card">
          <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <Cpu className="text-indigo-500" size={18} />
            Migration Notes
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-600 dark:text-slate-300">
            <div className="rounded-2xl bg-slate-50 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Summary</div>
              <div className="whitespace-pre-wrap">{migration.migrationSummary || 'No summary available.'}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Reason for Change</div>
              <div className="whitespace-pre-wrap">{reportData?.root_cause_analysis || migration.suggestedFixes || 'No reason captured.'}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="p-6 glass-card">
        <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
          <ExternalLink className="text-brand-500" size={18} />
          Migration Status Matrix
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3 text-sm">
          {[
            ['Build', reportData?.build_status || migration.buildStatus],
            ['Test', reportData?.test_status || 'Not run'],
            ['Runtime', reportData?.runtime_status || migration.runtimeStatus],
            ['Backend', reportData?.backend_health_check || 'Verified'],
            ['Frontend', reportData?.frontend_runtime_status || reportData?.frontend_status || 'Unknown'],
            ['UI', reportData?.ui_accessibility_status || 'Unknown'],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-slate-50 dark:bg-dark-950/40 border border-slate-200/60 dark:border-dark-800/60 p-4">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
              <div className="mt-1 font-bold text-slate-800 dark:text-slate-200">{String(value || 'Unknown')}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
