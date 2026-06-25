import React, { useState, useEffect } from 'react';
import { RefreshCw, Play, FileText, CheckCircle, ShieldAlert, Cpu, Download, Clock, Trash2, Server, Terminal, ExternalLink, Copy, Search, StopCircle, Globe, Check } from 'lucide-react';
import { migrateRepository, getMigrationReportUrl, getMigrationStatus, startProject, stopProject, getProjectStatus } from '../api';
import Prism from 'prismjs';

const parseGitDiff = (diffStr) => {
  if (!diffStr) return [];
  const lines = diffStr.split('\n');
  const files = [];
  let currentFile = null;
  let oldLineNum = 0;
  let newLineNum = 0;

  lines.forEach(line => {
    if (line.startsWith('diff --git')) {
      if (currentFile) files.push(currentFile);
      currentFile = { name: line.split(' b/')[1] || line, lines: [] };
    } else if (line.startsWith('@@ ')) {
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLineNum = parseInt(match[1], 10);
        newLineNum = parseInt(match[2], 10);
        currentFile.lines.push({ type: 'chunk', content: line });
      }
    } else if (currentFile) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentFile.lines.push({ type: 'add', content: line, newNum: newLineNum++ });
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentFile.lines.push({ type: 'remove', content: line, oldNum: oldLineNum++ });
      } else if (!line.startsWith('---') && !line.startsWith('+++') && !line.startsWith('index ')) {
        currentFile.lines.push({ type: 'context', content: line, oldNum: oldLineNum++, newNum: newLineNum++ });
      }
    }
  });
  if (currentFile) files.push(currentFile);
  return files;
};

export default function MigrationCenter({ 
  setActiveTab, 
  analysisResult,
  repoUrl,
  setRepoUrl,
  targetVersion,
  setTargetVersion,
  loading,
  setLoading,
  result,
  setResult,
  error,
  setError,
  statusText,
  setStatusText,
  history,
  setHistory,
  elapsedTime,
  timeTaken,
  setTimeTaken
}) {
  const repoName = repoUrl ? repoUrl.split('/').pop().replace('.git', '') : '';

  const [runnerStatus, setRunnerStatus] = useState('IDLE');
  const [runnerPort, setRunnerPort] = useState(null);
  const [runnerType, setRunnerType] = useState(null);
  const [runnerPreviewUrl, setRunnerPreviewUrl] = useState(null);
  const [runnerEndpoints, setRunnerEndpoints] = useState([]);
  const [runnerErrorReason, setRunnerErrorReason] = useState(null);
  const [iframeKey, setIframeKey] = useState(0);
  const [runnerLogs, setRunnerLogs] = useState('');
  const [runnerLoading, setRunnerLoading] = useState(false);
  const [activePreviewTab, setActivePreviewTab] = useState('logs');
  const [copiedPath, setCopiedPath] = useState(null);
  const [endpointSearch, setEndpointSearch] = useState('');

  const getPreviewSrc = (previewUrl) => {
    if (!previewUrl) return null;

    try {
      const parsed = new URL(previewUrl, window.location.origin);
      if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') {
        return repoName ? `/api/run/preview/${repoName}` : parsed.pathname;
      }
    } catch (e) {
      if (previewUrl.startsWith('/')) {
        return previewUrl;
      }
    }

    return previewUrl;
  };

  const previewSrc = getPreviewSrc(runnerPreviewUrl);
  const previewBaseUrl = previewSrc || (runnerPort ? `http://localhost:${runnerPort}` : '');

  const setupLogsWebSocket = () => {
    if (!repoName) return;
    const wsUrl = `ws://localhost:8000/api/ws/run/logs/${repoName}`;
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      setRunnerLogs(prev => prev + event.data);
      const consoleElem = document.getElementById('runner-console');
      if (consoleElem) {
        consoleElem.scrollTop = consoleElem.scrollHeight;
      }
    };
    
    ws.onerror = (err) => {
      console.error("Runner WebSocket error:", err);
    };
    
    return ws;
  };

  const startRunnerPolling = () => {
    if (!repoName) return;
    
    const interval = setInterval(async () => {
      try {
        const data = await getProjectStatus(repoName);
        setRunnerStatus(data.status);
        setRunnerPort(data.port);
        setRunnerType(data.projectType);
        setRunnerPreviewUrl(data.previewUrl);
        setRunnerEndpoints(data.endpoints || []);
        setRunnerErrorReason(data.errorReason);
        
        if (data.status === 'RUNNING') {
          setActivePreviewTab('preview');
        }
        
        if (data.status !== 'STARTING') {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Error polling project runner:", err);
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  };

  useEffect(() => {
    let cleanupPoll = () => {};
    if (repoName && result && result.buildStatus === 'Build Success') {
      const checkInitialStatus = async () => {
        try {
          const data = await getProjectStatus(repoName);
          setRunnerStatus(data.status);
          setRunnerPort(data.port);
          setRunnerType(data.projectType);
          setRunnerPreviewUrl(data.previewUrl);
          setRunnerEndpoints(data.endpoints || []);
          setRunnerErrorReason(data.errorReason);
          
          if (data.status === 'STARTING') {
            setupLogsWebSocket();
            cleanupPoll = startRunnerPolling();
          } else if (data.status === 'RUNNING') {
            setupLogsWebSocket();
            setActivePreviewTab('preview');
          }
        } catch (err) {
          console.error(err);
        }
      };
      checkInitialStatus();
    }
    return () => cleanupPoll();
  }, [repoName, result]);

  const handleStartProject = async () => {
    if (!repoName) return;
    setRunnerLoading(true);
    setRunnerLogs('Starting application...\n');
    setRunnerErrorReason(null);
    setActivePreviewTab('logs');
    try {
      const data = await startProject(repoName);
      setRunnerStatus(data.status);
      setRunnerPort(data.port);
      setRunnerType(data.projectType);
      setupLogsWebSocket();
      startRunnerPolling();
    } catch (err) {
      console.error(err);
      setRunnerStatus('FAILED');
      setRunnerErrorReason(err.message || 'Failed to start the application server.');
    } finally {
      setRunnerLoading(false);
    }
  };

  const handleStopProject = async () => {
    if (!repoName) return;
    setRunnerLoading(true);
    try {
      await stopProject(repoName);
      setRunnerStatus('STOPPED');
      setRunnerPreviewUrl(null);
      setRunnerEndpoints([]);
    } catch (err) {
      console.error(err);
    } finally {
      setRunnerLoading(false);
    }
  };

  const handleRestartProject = async () => {
    if (!repoName) return;
    setRunnerLoading(true);
    setRunnerLogs('Restarting application...\n');
    setRunnerErrorReason(null);
    setIframeKey(prev => prev + 1);
    try {
      await stopProject(repoName);
      const data = await startProject(repoName);
      setRunnerStatus(data.status);
      setRunnerPort(data.port);
      setRunnerType(data.projectType);
      setupLogsWebSocket();
      startRunnerPolling();
    } catch (err) {
      setRunnerErrorReason(err.response?.data?.detail || err.message || 'Unknown error');
      setRunnerStatus('FAILED');
    } finally {
      setRunnerLoading(false);
    }
  };

  const handleRefreshPreview = () => {
    setIframeKey(prev => prev + 1);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedPath(text);
    setTimeout(() => setCopiedPath(null), 2000);
  };

  const handleMigrate = async (e) => {
    e.preventDefault();
    if (!repoUrl) {
      setError("Please perform Repository Analysis first to load a repository.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setTimeTaken(null);
    setStatusText('Queuing migration task...');

    const startTime = Date.now();

    try {
      const taskData = await migrateRepository(repoUrl, targetVersion);
      const taskId = taskData.task_id;

      setStatusText('Migration task is running in the background...');

      const pollStatus = async () => {
        try {
          const statusData = await getMigrationStatus(taskId);
          
          if (statusData.status === 'SUCCESS') {
            const data = statusData.result;
            const endTime = Date.now();
            const duration = ((endTime - startTime) / 1000).toFixed(1);

            if (data.errorMessage) {
              setError(data.errorMessage);
            } else {
              setResult(data);
              setTimeTaken(duration);
              localStorage.setItem('last_migration_time', JSON.stringify(duration));
              localStorage.setItem('last_migration', JSON.stringify(data));

              // Add to migration history
              const historyEntry = {
                id: Date.now(),
                repoUrl,
                targetVersion: data.targetVersion,
                success: data.success,
                buildStatus: data.buildStatus,
                modifiedFiles: data.modifiedFiles?.length || 0,
                timestamp: new Date().toLocaleString(),
              };
              const updatedHistory = [historyEntry, ...history].slice(0, 20); // Keep last 20
              setHistory(updatedHistory);
              localStorage.setItem('migration_history', JSON.stringify(updatedHistory));
              
              // Update stats
              const stats = JSON.parse(localStorage.getItem('assistant_stats') || '{"reposAnalyzed":0,"migrationsRun":0,"filesConverted":0}');
              stats.migrationsRun += 1;
              localStorage.setItem('assistant_stats', JSON.stringify(stats));
            }
            setLoading(false);
          } else if (statusData.status === 'FAILURE') {
            setError(statusData.error || 'Migration task failed in the background queue.');
            setLoading(false);
          } else {
            // Still PENDING or RUNNING
            setTimeout(pollStatus, 3000);
          }
        } catch (err) {
          setError(err.response?.data?.message || err.message || 'Error polling migration status.');
          setLoading(false);
        }
      };

      setTimeout(pollStatus, 3000);

    } catch (err) {
      setError(err.response?.data?.message || err.message || 'An error occurred during repository migration queueing.');
      setLoading(false);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem('migration_history');
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Parameter Form */}
      <div className="p-6 glass-card">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-2">
          <RefreshCw className="text-brand-500 animate-spin-slow" size={22} />
          Automated Java Migration Center
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          Upgrades class files, deprecations, compilation release levels, and library definitions using OpenRewrite.
        </p>

        {repoUrl ? (
          <div className="p-4 rounded-xl bg-slate-100/50 dark:bg-dark-900/40 border border-slate-200/30 dark:border-dark-800/40 mb-6 text-sm">
            <span className="font-semibold text-slate-400">Target Project:</span>{' '}
            <span className="font-bold text-indigo-600 dark:text-indigo-400">{repoUrl}</span>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-sm mb-6 font-medium">
            ⚠️ No project analysis loaded. Please run the Repository Analysis first.
          </div>
        )}

        <form onSubmit={handleMigrate} className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-slate-500 dark:text-slate-400 mb-2">
              Select Target Java Version
            </label>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl">
              <label className={`p-4 rounded-xl border flex items-center gap-3 cursor-pointer transition-all ${
                targetVersion === '11' 
                  ? 'border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-400' 
                  : 'border-slate-200 dark:border-dark-800 bg-transparent hover:bg-slate-100/30'
              }`}>
                <input
                  type="radio"
                  name="targetVersion"
                  value="11"
                  checked={targetVersion === '11'}
                  onChange={() => setTargetVersion('11')}
                  className="hidden"
                />
                <span className="font-bold text-lg">Java 11</span>
                <span className="text-xs opacity-75">(Older LTS)</span>
              </label>

              <label className={`p-4 rounded-xl border flex items-center gap-3 cursor-pointer transition-all ${
                targetVersion === '17' 
                  ? 'border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-400' 
                  : 'border-slate-200 dark:border-dark-800 bg-transparent hover:bg-slate-100/30'
              }`}>
                <input
                  type="radio"
                  name="targetVersion"
                  value="17"
                  checked={targetVersion === '17'}
                  onChange={() => setTargetVersion('17')}
                  className="hidden"
                />
                <span className="font-bold text-lg">Java 17</span>
                <span className="text-xs opacity-75">(LTS Baseline)</span>
              </label>

              <label className={`p-4 rounded-xl border flex items-center gap-3 cursor-pointer transition-all ${
                targetVersion === '21' 
                  ? 'border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-400' 
                  : 'border-slate-200 dark:border-dark-800 bg-transparent hover:bg-slate-100/30'
              }`}>
                <input
                  type="radio"
                  name="targetVersion"
                  value="21"
                  checked={targetVersion === '21'}
                  onChange={() => setTargetVersion('21')}
                  className="hidden"
                />
                <span className="font-bold text-lg">Java 21</span>
                <span className="text-xs opacity-75">(Virtual Threads)</span>
              </label>

              <label className={`p-4 rounded-xl border flex items-center gap-3 cursor-pointer transition-all ${
                targetVersion === '25' 
                  ? 'border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-400' 
                  : 'border-slate-200 dark:border-dark-800 bg-transparent hover:bg-slate-100/30'
              }`}>
                <input
                  type="radio"
                  name="targetVersion"
                  value="25"
                  checked={targetVersion === '25'}
                  onChange={() => setTargetVersion('25')}
                  className="hidden"
                />
                <span className="font-bold text-lg">Java 25</span>
                <span className="text-xs opacity-75">(Next LTS)</span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !repoUrl}
            className="flex items-center justify-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm font-sans"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Processing Migration... ({elapsedTime}s)
              </>
            ) : (
              <>
                <Play size={16} /> Run Migration & Verify
              </>
            )}
          </button>
        </form>

        {loading && (
          <div className="mt-6 p-4 rounded-xl border border-indigo-100 dark:border-indigo-950 bg-indigo-50/30 dark:bg-indigo-950/20 text-sm text-indigo-700 dark:text-indigo-300 font-semibold animate-pulse">
            Status: {statusText} ({elapsedTime}s)
          </div>
        )}

        {timeTaken && result && !loading && (
          <div className="mt-6 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-sm font-semibold flex items-center gap-2 font-sans">
            <CheckCircle size={18} className="text-emerald-500" />
            Migration & compiler verification completed in {timeTaken}s.
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-400 glass-card flex gap-3 items-start">
          <ShieldAlert size={24} className="flex-shrink-0" />
          <div>
            <h4 className="font-bold text-sm">Migration Failed</h4>
            <p className="mt-1 text-xs leading-relaxed">{error}</p>
          </div>
        </div>
      )}

      {/* Migration results */}
      {result && (
        <>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Main Console details */}
          <div className="lg:col-span-2 space-y-6">
            <div className="p-6 glass-card">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <FileText className="text-indigo-500" size={18} />
                  OpenRewrite Execution Log
                </h3>
                <span className={`px-3 py-1 text-xs font-bold rounded-full border ${
                  result.success 
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400' 
                    : 'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400'
                }`}>
                  {result.success ? 'Recipes Executed' : 'Execution Notice'}
                </span>
              </div>
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto max-h-96 leading-relaxed">
                {result.migrationSummary || 'No log details generated.'}
              </pre>
            </div>

            {/* Build validation logs if failed */}
            {result.buildErrors && (
              <div className="p-6 glass-card border-rose-500/20">
                <h3 className="text-md font-bold text-rose-500 flex items-center gap-2 mb-4">
                  <ShieldAlert size={18} />
                  Compiler Error Log
                </h3>
                <pre className="p-4 rounded-xl bg-rose-950/20 text-rose-300 border border-rose-500/10 text-xs font-mono overflow-x-auto max-h-80 leading-relaxed">
                  {result.buildErrors}
                </pre>
              </div>
            )}
          </div>

            {/* Validation & Actions panel */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-6 glass-card">
              <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center justify-between">
                Build Check & Verification
                {result.usedProvider && result.usedProvider !== 'gemini' && (
                  <span className="px-2 py-0.5 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[9px] font-bold rounded border border-amber-500/20 uppercase tracking-wider">
                    Fallback: {result.usedProvider}
                  </span>
                )}
              </h3>
              <div className={`p-4 rounded-xl flex items-center gap-3 border ${
                result.buildStatus === 'Build Success'
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400'
                  : 'bg-rose-500/10 border-rose-500/20 text-rose-700 dark:text-rose-400'
              }`}>
                {result.buildStatus === 'Build Success' ? <CheckCircle size={20} /> : <ShieldAlert size={20} />}
                <div className="text-sm font-bold">{result.buildStatus}</div>
              </div>

              <h4 className="text-xs font-semibold text-slate-400 mt-6 mb-3 uppercase tracking-wider">Modified Files</h4>
              <div className="max-h-48 overflow-y-auto space-y-2 border border-slate-100 dark:border-dark-800 rounded-xl p-3 bg-slate-50/50 dark:bg-dark-900/10">
                {result.modifiedFiles.length > 0 ? (
                  result.modifiedFiles.map((file, idx) => (
                    <div key={idx} className="text-xs font-mono truncate text-slate-600 dark:text-slate-400">
                      📄 {file}
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-400 italic">No files modified</div>
                )}
              </div>
            </div>

            {/* Self-Healing Fix History */}
            {result.fixHistory && result.fixHistory.length > 0 && (
              <div className="p-6 glass-card border-brand-500/20">
                <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                  <RefreshCw className="text-brand-500" size={18} />
                  Self-Healing Execution Log
                </h3>
                <div className="space-y-4">
                  {result.fixHistory.map((history, idx) => (
                    <div key={idx} className="bg-slate-50 dark:bg-dark-950/20 p-4 rounded-xl border border-slate-200/30 dark:border-dark-900/30">
                      <div className="font-bold text-xs text-brand-600 dark:text-brand-400 mb-2">Attempt #{history.attempt}</div>
                      <div className="space-y-2">
                        {history.fixes.map((fix, fidx) => (
                          <div key={fidx} className="text-xs font-mono text-slate-600 dark:text-slate-400 border-l-2 border-brand-500 pl-2">
                            <div>📄 {fix.file}</div>
                            <div className="text-emerald-600 dark:text-emerald-400">✓ Applied automated fix</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Fix Suggestions */}
            {result.suggestedFixes && (
              <div className="p-6 glass-card">
                <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                  <Cpu className="text-indigo-500" size={18} />
                  AI Compile Recommendations
                </h3>
                <div className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-dark-950/20 p-4 rounded-xl border border-slate-200/30 dark:border-dark-900/30 whitespace-pre-wrap">
                  {result.suggestedFixes}
                </div>
              </div>
            )}

            {/* Reports Link */}
            <div className="p-6 glass-card space-y-3">
              <h3 className="text-md font-bold text-slate-900 dark:text-white mb-2">Audit Reports</h3>
              <a
                href={getMigrationReportUrl()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-dark-800 dark:hover:bg-dark-700 text-slate-800 dark:text-slate-200 font-semibold rounded-xl text-xs transition-all border border-slate-200/50 dark:border-dark-700"
              >
                <Download size={14} /> Download PDF Report
              </a>
              <button
                onClick={() => setActiveTab('migrationReport')}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
              >
                View Migration Report
              </button>
            </div>
          </div>
        </div>
        
        {/* Project Execution Console */}
        {result.buildStatus === 'Build Success' && (
          <div className="mt-8 p-6 glass-card animate-fadeIn border border-indigo-500/10 shadow-lg">
            {/* Header section with controls */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200/50 dark:border-dark-800/50 pb-6 mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-indigo-500/10 text-indigo-500 rounded-2xl border border-indigo-500/20">
                  <Server size={22} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    Project Runner Dashboard
                  </h3>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                    Automatically installs dependencies, resolves ports, parses REST API controllers, and launches the migrated app.
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-4 flex-wrap">
                {/* Status Badges */}
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400">Status:</span>
                  {runnerStatus === 'IDLE' && (
                    <span className="px-2.5 py-1 bg-slate-100 dark:bg-dark-800 text-slate-700 dark:text-slate-300 font-bold rounded-lg border border-slate-200/50 dark:border-dark-700">
                      IDLE
                    </span>
                  )}
                  {runnerStatus === 'STARTING' && (
                    <span className="px-2.5 py-1 bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold rounded-lg border border-amber-500/20 animate-pulse flex items-center gap-1.5">
                      <RefreshCw size={12} className="animate-spin" /> STARTING
                    </span>
                  )}
                  {runnerStatus === 'RUNNING' && (
                    <span className="px-2.5 py-1 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold rounded-lg border border-emerald-500/20 flex items-center gap-1.5 shadow-[0_0_12px_rgba(16,185,129,0.15)]">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" /> RUNNING
                    </span>
                  )}
                  {runnerStatus === 'FAILED' && (
                    <span className="px-2.5 py-1 bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold rounded-lg border border-rose-500/20">
                      FAILED
                    </span>
                  )}
                  {runnerStatus === 'STOPPED' && (
                    <span className="px-2.5 py-1 bg-slate-500/10 text-slate-500 dark:text-slate-400 font-bold rounded-lg border border-slate-500/20">
                      STOPPED
                    </span>
                  )}
                </div>

                {runnerPort && (
                  <div className="text-xs bg-slate-100 dark:bg-dark-800/80 px-2.5 py-1 rounded-lg border border-slate-200/40 dark:border-dark-700/40">
                    <span className="text-slate-400">Port:</span> <span className="font-bold font-mono text-indigo-500">{runnerPort}</span>
                  </div>
                )}

                {runnerType && (
                  <div className="text-xs bg-slate-100 dark:bg-dark-800/80 px-2.5 py-1 rounded-lg border border-slate-200/40 dark:border-dark-700/40">
                    <span className="text-slate-400">Type:</span> <span className="font-bold text-slate-600 dark:text-slate-300">{runnerType}</span>
                  </div>
                )}

                {/* Primary Action Buttons */}
                {runnerStatus === 'IDLE' || runnerStatus === 'STOPPED' || runnerStatus === 'FAILED' ? (
                  <button
                    onClick={handleStartProject}
                    disabled={runnerLoading}
                    className="flex items-center gap-1.5 px-5 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-bold rounded-xl text-xs shadow-md transition-all disabled:opacity-50"
                  >
                    <Play size={12} fill="currentColor" /> Run Project
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <button
                      onClick={handleRestartProject}
                      disabled={runnerLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl text-xs shadow-md transition-all disabled:opacity-50"
                    >
                      <RefreshCw size={12} /> Restart
                    </button>
                    <button
                      onClick={handleStopProject}
                      disabled={runnerLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white font-bold rounded-xl text-xs shadow-md transition-all disabled:opacity-50"
                    >
                      <StopCircle size={12} /> Stop
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Split Screen Dashboard */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[600px]">
              
              {/* Left Side: Logs & Status */}
              <div className="flex flex-col h-full border border-slate-200/40 dark:border-dark-900/40 rounded-2xl overflow-hidden bg-slate-950/20 dark:bg-dark-950/20">
                <div className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 dark:bg-dark-950 text-white border-b border-slate-800 text-xs font-bold shrink-0">
                  <Terminal size={14} /> Log Console
                </div>
                <div className="relative flex-grow bg-slate-950 p-4 font-mono text-xs overflow-hidden flex flex-col">
                  <div className="absolute top-2 right-4 flex gap-2">
                    <button
                      onClick={() => setRunnerLogs('')}
                      className="px-2 py-1 bg-slate-800/80 hover:bg-slate-700/80 text-[10px] text-slate-300 font-bold rounded transition-colors"
                    >
                      Clear
                    </button>
                    <button
                      onClick={() => copyToClipboard(runnerLogs)}
                      className="px-2 py-1 bg-slate-800/80 hover:bg-slate-700/80 text-[10px] text-slate-300 font-bold rounded transition-colors flex items-center gap-1"
                    >
                      {copiedPath === runnerLogs ? <Check size={10} /> : <Copy size={10} />} Copy
                    </button>
                  </div>
                  <pre
                    id="runner-console"
                    className="flex-grow w-full overflow-y-auto leading-relaxed text-slate-200 whitespace-pre-wrap select-text pr-2 scrollbar-thin text-left"
                  >
                    {runnerLogs || 'Console idle. Click Run Project above to boot server...'}
                  </pre>
                </div>
              </div>

              {/* Right Side: Live App Preview */}
              <div className="flex flex-col h-full border border-slate-200/40 dark:border-dark-900/40 rounded-2xl overflow-hidden bg-white dark:bg-dark-950">
                <div className="flex items-center justify-between px-4 py-2 bg-indigo-600 text-white text-xs font-bold shrink-0">
                  <div className="flex items-center gap-1.5">
                    <Globe size={14} /> Live Application Preview
                  </div>
                  {(runnerStatus === 'RUNNING' || runnerStatus === 'STARTING') && (
                    <button onClick={handleRefreshPreview} className="hover:text-indigo-200 transition-colors flex items-center gap-1">
                      <RefreshCw size={12} /> Refresh
                    </button>
                  )}
                </div>
                
                <div className="flex-grow relative bg-slate-50 dark:bg-dark-900 overflow-hidden flex flex-col">
                  {runnerStatus === 'FAILED' ? (
                    <div className="p-6 h-full overflow-auto">
                      <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 text-sm leading-relaxed flex flex-col gap-3">
                        <div className="flex items-center gap-2 font-bold text-base">
                          <ShieldAlert size={20} className="flex-shrink-0" /> Startup Failed
                        </div>
                        <p>{runnerErrorReason}</p>
                        <div className="mt-4 pt-4 border-t border-rose-500/20">
                          <p className="font-semibold mb-2">Troubleshooting Steps:</p>
                          <ul className="list-disc pl-4 space-y-2 text-rose-600/80 dark:text-rose-400/80">
                            <li>Check Database: Is the database running and credentials in `application.properties`/`application.yml` matching?</li>
                            <li>Environment Variables: Ensure any required `.env` entries are defined.</li>
                            <li>Port Conflicts: Ensure port {runnerPort || '8080'} is not occupied by another app.</li>
                            <li>View the Log Console on the left for detailed stack traces.</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  ) : runnerStatus === 'STARTING' ? (
                    <div className="flex items-center justify-center h-full flex-col text-slate-400 gap-4">
                      <RefreshCw size={32} className="animate-spin text-indigo-500 opacity-50" />
                      <p className="font-semibold">Building and starting application...</p>
                    </div>
                  ) : runnerStatus === 'IDLE' || runnerStatus === 'STOPPED' ? (
                    <div className="flex items-center justify-center h-full text-slate-400 font-semibold">
                      Click Run Project to start the preview
                    </div>
                  ) : runnerEndpoints && runnerEndpoints.length > 0 && !runnerPreviewUrl ? (
                    <div className="flex-grow p-4 overflow-hidden flex flex-col">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 shrink-0">
                        <div className="text-left">
                          <h4 className="font-bold text-sm text-slate-800 dark:text-slate-200 mb-1 flex items-center gap-2">
                            <Cpu size={16} className="text-brand-500" /> API Endpoints Ready
                          </h4>
                          <p className="text-xs text-slate-400">
                            Swagger documentation is available at: {' '}
                            <a
                              href={`${previewBaseUrl}/swagger-ui/index.html`}
                              target="_blank"
                              rel="noreferrer"
                              className="font-mono text-indigo-500 hover:underline font-bold"
                            >
                              {previewBaseUrl}/swagger-ui/index.html
                            </a>
                          </p>
                        </div>

                        <div className="relative max-w-xs w-full">
                          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                          <input
                            type="text"
                            placeholder="Search routes..."
                            value={endpointSearch}
                            onChange={(e) => setEndpointSearch(e.target.value)}
                            className="w-full text-xs pl-9 pr-4 py-2 bg-slate-50 dark:bg-dark-900 border border-slate-200 dark:border-dark-800 rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500 font-medium text-slate-700 dark:text-slate-300"
                          />
                        </div>
                      </div>

                      <div className="overflow-auto flex-grow border border-slate-100 dark:border-dark-900 rounded-xl bg-slate-50/50 dark:bg-dark-950/20 scrollbar-thin">
                        <table className="w-full text-xs text-left border-collapse">
                          <thead>
                            <tr className="border-b border-slate-200/50 dark:border-dark-900/50 bg-slate-100/40 dark:bg-dark-900/40 font-bold text-slate-500 sticky top-0 backdrop-blur-md">
                              <th className="p-3 w-24">Method</th>
                              <th className="p-3">Route Endpoint</th>
                              <th className="p-3 w-40">Controller Class</th>
                              <th className="p-3 w-20 text-center">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {runnerEndpoints
                              .filter(ep => ep.path.toLowerCase().includes(endpointSearch.toLowerCase()))
                              .map((ep, idx) => (
                                <tr key={idx} className="border-b border-slate-100 dark:border-dark-900/30 hover:bg-slate-100/20 dark:hover:bg-dark-900/20 transition-colors">
                                  <td className="p-3">
                                    <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                                      ep.method === 'GET' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
                                      ep.method === 'POST' ? 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' :
                                      ep.method === 'PUT' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                                      ep.method === 'DELETE' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
                                      'bg-slate-500/10 text-slate-600 dark:text-slate-400'
                                    }`}>
                                      {ep.method}
                                    </span>
                                  </td>
                                  <td className="p-3 font-mono font-bold text-slate-700 dark:text-slate-300">
                                    {ep.path}
                                  </td>
                                  <td className="p-3 font-mono text-slate-400 truncate max-w-[150px]">
                                    {ep.file}
                                  </td>
                                  <td className="p-3 text-center">
                                    <button
                                      onClick={() => copyToClipboard(`${previewBaseUrl}${ep.path}`)}
                                      className="text-slate-400 hover:text-indigo-500 p-1 bg-slate-100 dark:bg-dark-900 rounded border border-slate-200/50 dark:border-dark-800 transition-colors"
                                      title="Copy absolute URL"
                                    >
                                      {copiedPath === `${previewBaseUrl}${ep.path}` ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                                    </button>
                                  </td>
                                </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : previewSrc ? (
                    <iframe
                      key={iframeKey}
                      src={previewSrc}
                      title="Live App Preview"
                      className="w-full h-full border-0 bg-white"
                      sandbox="allow-same-origin allow-scripts allow-forms"
                    />
                  ) : null}

              </div>
            </div>
          </div>
        </div>
      )}
      </>
    )}

      {/* GitHub-Style Diff Viewer */}
      {result && result.gitDiff && (
        <div className="p-6 glass-card animate-fadeIn">
          <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
            <FileText className="text-brand-500" size={18} />
            Migration Changes (Pull Request View)
          </h3>
          <div className="border border-slate-200 dark:border-dark-800 rounded-xl overflow-hidden bg-white dark:bg-dark-950">
            {parseGitDiff(result.gitDiff).map((file, idx) => (
              <div key={idx} className="mb-4 last:mb-0">
                <div className="bg-slate-100 dark:bg-dark-900 px-4 py-2 border-b border-slate-200 dark:border-dark-800 font-mono text-xs font-bold text-slate-700 dark:text-slate-300">
                  {file.name}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left border-collapse">
                    <tbody>
                      {file.lines.map((line, lidx) => (
                        <tr key={lidx} className={
                          line.type === 'add' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' :
                          line.type === 'remove' ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400' :
                          line.type === 'chunk' ? 'bg-indigo-500/5 text-indigo-500 font-bold' :
                          'text-slate-600 dark:text-slate-400'
                        }>
                          <td className="px-2 py-0.5 whitespace-pre border-r border-slate-200 dark:border-dark-800/50 w-8 text-right text-slate-400 select-none">
                            {line.oldNum || ''}
                          </td>
                          <td className="px-2 py-0.5 whitespace-pre border-r border-slate-200 dark:border-dark-800/50 w-8 text-right text-slate-400 select-none">
                            {line.newNum || ''}
                          </td>
                          <td className="px-4 py-0.5 whitespace-pre w-full break-all">
                            {line.content}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Migration History */}
      {history.length > 0 && (
        <div className="p-6 glass-card animate-fadeIn">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Clock className="text-brand-500" size={18} />
              Migration History
            </h3>
            <button
              onClick={clearHistory}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 transition-colors rounded-lg hover:bg-rose-500/10"
            >
              <Trash2 size={12} /> Clear
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-200/50 dark:border-dark-800/50">
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Repository</th>
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Target</th>
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Migration</th>
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Build</th>
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Files Changed</th>
                  <th className="py-3 px-3 font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((entry) => (
                  <tr key={entry.id} className="border-b border-slate-100/50 dark:border-dark-800/30 hover:bg-slate-50/50 dark:hover:bg-dark-900/20 transition-colors">
                    <td className="py-3 px-3 font-mono text-indigo-600 dark:text-indigo-400 truncate max-w-[200px]">
                      {entry.repoUrl?.split('/').slice(-1)[0] || entry.repoUrl}
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 bg-brand-500/10 text-brand-600 dark:text-brand-400 rounded-md font-bold">
                        Java {entry.targetVersion}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded-md font-bold ${
                        entry.success
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                      }`}>
                        {entry.success ? 'Success' : 'Partial'}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded-md font-bold ${
                        (entry.buildStatus === 'Build Success' || entry.buildStatus === 'Success')
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                      }`}>
                        {entry.buildStatus}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center font-bold text-slate-600 dark:text-slate-400">
                      {entry.modifiedFiles}
                    </td>
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                      {entry.timestamp}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
