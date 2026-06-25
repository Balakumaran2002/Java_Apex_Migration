import React, { useState, useEffect } from 'react';
import { Terminal, Cpu, Database, CheckCircle, ArrowRight, Zap, RefreshCw } from 'lucide-react';
import { getStatus } from '../api';

export default function Dashboard({ setActiveTab }) {
  const [status, setStatus] = useState({ ragInitialized: false, ragMessage: '', provider: '' });
  const [stats, setStats] = useState({
    reposAnalyzed: 0,
    migrationsRun: 0,
    filesConverted: 0,
  });

  useEffect(() => {
    // Load statistics from localStorage
    const localStats = JSON.parse(localStorage.getItem('assistant_stats') || '{"reposAnalyzed":0,"migrationsRun":0,"filesConverted":0}');
    setStats(localStats);

    // Fetch backend RAG status with polling
    const fetchStatus = () => {
      getStatus()
        .then(data => setStatus(data))
        .catch(err => {
          console.error("Error fetching status:", err);
          setStatus({ ragInitialized: false, ragMessage: 'Disconnected from backend. Retrying...', provider: '' });
        });
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden p-8 rounded-3xl bg-gradient-to-r from-brand-600 to-indigo-700 text-white shadow-xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full blur-3xl -mr-20 -mt-20 animate-pulse-slow"></div>
        <div className="relative z-10 max-w-2xl">
          <span className="px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-white/20 rounded-full">
            Enterprise Migration Assistant
          </span>
          <h1 className="mt-4 text-3xl md:text-4xl font-extrabold tracking-tight">
            AI-Powered Java Migration & Conversion
          </h1>
          <p className="mt-2 text-indigo-100 text-base leading-relaxed">
            Automate code updates, perform semantic RAG audits, upgrade legacy structures, and translate Java packages to clean Python source files in seconds.
          </p>
          <div className="mt-6 flex flex-wrap gap-4">
            <button
              onClick={() => setActiveTab('analysis')}
              className="flex items-center gap-2 px-5 py-2.5 bg-white text-indigo-900 font-semibold rounded-xl hover:bg-slate-100 shadow-md hover:shadow-lg transition-all"
            >
              Analyze Repository <ArrowRight size={16} />
            </button>
            <button
              onClick={() => setActiveTab('conversion')}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-800/50 hover:bg-indigo-800/80 border border-white/20 text-white font-semibold rounded-xl transition-all"
            >
              Convert Java Code <Zap size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* RAG Engine Status Alert */}
      <div className={`p-4 rounded-2xl flex items-center gap-3 border ${
        status.ragInitialized 
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400' 
          : 'bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-400'
      } glass-card`}>
        <Cpu className={status.ragInitialized ? 'text-emerald-500' : 'text-amber-500'} size={20} />
        <div className="flex-1 text-sm font-medium">
          <span className="font-bold">Local RAG Engine:</span> {status.ragMessage}
        </div>
        <span className="flex h-2 w-2 relative">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${status.ragInitialized ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
          <span className={`relative inline-flex rounded-full h-2 w-2 ${status.ragInitialized ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
        </span>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 glass-card hover:scale-[1.02]">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">Repositories Processed</p>
              <h3 className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white">{stats.reposAnalyzed}</h3>
            </div>
            <div className="p-3 bg-brand-500/10 text-brand-600 dark:text-brand-400 rounded-xl">
              <Database size={24} />
            </div>
          </div>
          <p className="mt-4 text-xs text-slate-400">Total GitHub projects cloned and analyzed</p>
        </div>

        <div className="p-6 glass-card hover:scale-[1.02]">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">Java Migrations Applied</p>
              <h3 className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white">{stats.migrationsRun}</h3>
            </div>
            <div className="p-3 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl">
              <RefreshCw size={24} />
            </div>
          </div>
          <p className="mt-4 text-xs text-slate-400">OpenRewrite Java recipes executed successfully</p>
        </div>

        <div className="p-6 glass-card hover:scale-[1.02]">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">Files Converted</p>
              <h3 className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white">{stats.filesConverted}</h3>
            </div>
            <div className="p-3 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
              <Terminal size={24} />
            </div>
          </div>
          <p className="mt-4 text-xs text-slate-400">Java files parsed and rewritten into Python</p>
        </div>
      </div>

      {/* Feature Walkthrough */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
          <CheckCircle size={20} className="text-indigo-500" />
          Migration Capabilities & Supported Workflows
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-4 rounded-xl border border-slate-200/40 dark:border-dark-800/40 bg-slate-100/50 dark:bg-dark-900/30">
            <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
              Modern Java Upgrades
            </h4>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
              Automate migration paths from Java 8 or 11 up to Java 17 and Java 21. OpenRewrite recipes rewrite compiler settings, package names, deprecations, and Jakarta EE namespaces.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-200/40 dark:border-dark-800/40 bg-slate-100/50 dark:bg-dark-900/30">
            <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
              Java to Python Transpiler
            </h4>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
              Leverage Gemini to parse entire Java class files, structures, collections, and custom loops. Generates side-by-side IDE comparison screens with direct ZIP file download links.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
