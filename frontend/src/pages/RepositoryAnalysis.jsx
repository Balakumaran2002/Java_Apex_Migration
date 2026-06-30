import React, { useState, useEffect } from 'react';
import { GitBranch, Play, CheckCircle, AlertTriangle, ShieldAlert, BookOpen, ArrowRight, Database, Package, Layers, Globe, Shield, Code, Server } from 'lucide-react';
import { analyzeRepository, getStatus } from '../api';

export default function RepositoryAnalysis({ 
  setActiveTab, 
  repoUrl, 
  setRepoUrl, 
  loading, 
  setLoading, 
  result, 
  setResult, 
  error, 
  setError, 
  statusText, 
  setStatusText,
  elapsedTime,
  timeTaken,
  setTimeTaken
}) {
  const [llmStatus, setLlmStatus] = useState(null);

  useEffect(() => {
    if (!loading) return undefined;
    let active = true;
    const poll = async () => {
      try {
        const data = await getStatus();
        if (!active) return;
        setLlmStatus(data.llmStatus || null);
        const currentJob = data.llmStatus?.currentJob;
        if (currentJob?.message) {
          setStatusText(currentJob.message);
        }
      } catch (e) {
        // ignore transient polling errors
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [loading, setStatusText]);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setTimeTaken(null);
    setStatusText('Connecting to repository...');

    const startTime = Date.now();

    // Small timer simulated log steps
    const timer = setTimeout(() => setStatusText('Cloning repository files...'), 1500);
    const timer2 = setTimeout(() => setStatusText('Detecting project properties and files...'), 3500);
    const timer3 = setTimeout(() => setStatusText('Extracting dependency tree...'), 5500);
    const timer4 = setTimeout(() => setStatusText('Querying local RAG knowledge base & consult AI...'), 7500);

    try {
      const data = await analyzeRepository(repoUrl);
      clearTimeout(timer);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      if (data.errorMessage) {
        setError(data.errorMessage);
      } else {
        setResult(data);
        setTimeTaken(duration);
        
        // Save to LocalStorage for persistence
        localStorage.setItem('last_analysis', JSON.stringify(data));
        localStorage.setItem('last_analysis_time', JSON.stringify(duration));
        
        // Update statistics
        const stats = JSON.parse(localStorage.getItem('assistant_stats') || '{"reposAnalyzed":0,"migrationsRun":0,"filesConverted":0}');
        stats.reposAnalyzed += 1;
        localStorage.setItem('assistant_stats', JSON.stringify(stats));
      }
    } catch (err) {
      clearTimeout(timer);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      setError(err.response?.data?.message || err.message || 'An error occurred during repository analysis.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Analysis Card */}
      <div className="p-6 glass-card">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-2">
          <GitBranch className="text-brand-500" size={22} />
          GitHub Repository Analysis
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          Submit a public GitHub repository link to inspect compiler configs, scan library versions, and get migration advice.
        </p>

        <form onSubmit={handleAnalyze} className="flex flex-col sm:flex-row gap-3">
          <input
            type="url"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/username/project-repo"
            required
            disabled={loading}
            className="flex-1 px-4 py-3 rounded-xl border border-slate-200 dark:border-dark-800 bg-white/50 dark:bg-dark-950/50 focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all text-sm"
          />
          <button
            type="submit"
            disabled={loading}
            className="flex items-center justify-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm whitespace-nowrap"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Analyzing... ({elapsedTime}s)
              </>
            ) : (
              <>
                <Play size={16} /> Run Audit
              </>
            )}
          </button>
        </form>

        {loading && (
          <div className="mt-6 p-4 rounded-xl border border-indigo-100 dark:border-indigo-950 bg-indigo-50/30 dark:bg-indigo-950/20 text-sm text-indigo-700 dark:text-indigo-300 font-semibold animate-pulse">
            Status: {statusText} ({elapsedTime}s)
          </div>
        )}

        {llmStatus?.currentJob?.totalChunks > 0 && (
          <div className="mt-4 p-4 rounded-xl border border-slate-200/60 dark:border-dark-800 bg-slate-50/60 dark:bg-dark-950/30 text-xs text-slate-600 dark:text-slate-300">
            Processing chunk {llmStatus.currentJob.currentChunk || 0} of {llmStatus.currentJob.totalChunks}
          </div>
        )}

        {timeTaken && result && !loading && (
          <div className="mt-6 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-sm font-semibold flex items-center gap-2 font-sans">
            <CheckCircle size={18} className="text-emerald-500" />
            Repository analysis completed in {timeTaken}s.
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-400 glass-card flex gap-3 items-start">
          <ShieldAlert size={24} className="flex-shrink-0" />
          <div>
            <h4 className="font-bold text-sm">Analysis Failed</h4>
            <p className="mt-1 text-xs leading-relaxed">{error}</p>
          </div>
        </div>
      )}

      {/* Result Display */}
      {result && (
        <div className="space-y-8 animate-fadeIn">
          {/* Validation Alert */}
          {result.projectType === 'Unknown' ? (
            <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 glass-card flex gap-3 items-start">
              <AlertTriangle size={24} className="flex-shrink-0" />
              <div>
                <h4 className="font-bold text-sm">Migration Not Applicable</h4>
                <p className="mt-1 text-xs leading-relaxed">{result.migrationRecommendation || 'Unrecognized project type.'}</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Properties Panel */}
              <div className="lg:col-span-1 space-y-6">
                <div className="p-6 glass-card">
                  <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4">Project Parameters</h3>
                  <table className="w-full text-xs text-left">
                    <tbody>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Language</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{result.projectType || 'Java'}</td>
                      </tr>
                      {result.detectedJavaVersion && (
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Java Version</td>
                        <td className="py-3 font-bold text-brand-600 dark:text-brand-400">Java {result.detectedJavaVersion}</td>
                      </tr>
                      )}
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Build Tool / PM</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{result.buildTool || 'Not Detected'}</td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Framework</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{result.frameworkType || (result.frameworkVersions && result.frameworkVersions["Spring Boot"] ? `Spring Boot ${result.frameworkVersions["Spring Boot"]}` : 'Not Detected')}</td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Database</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{result.database || 'None'}</td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Packaging</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200 uppercase">{result.packagingType || 'jar'}</td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Multi-module</td>
                        <td className={`py-3 font-bold ${result.isMultiModule ? 'text-amber-600 dark:text-amber-400' : 'text-slate-800 dark:text-slate-200'}`}>
                          {result.isMultiModule ? 'Yes' : 'No'}
                        </td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">Frontend</td>
                        <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{result.frontendFramework || (result.hasFrontend ? 'Detected' : 'None')}</td>
                      </tr>
                      <tr className="border-b border-slate-100 dark:border-dark-800">
                        <td className="py-3 font-semibold text-slate-400">API Endpoints</td>
                        <td className="py-3 font-bold text-indigo-600 dark:text-indigo-400">{result.endpointCount ?? 0} detected</td>
                      </tr>
                      <tr>
                        <td className="py-3 font-semibold text-slate-400">Risk Level</td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${
                            result.riskLevel === 'High' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                            : result.riskLevel === 'Medium' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                            : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          }`}>{result.riskLevel || 'Low'}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {(result.llmUsage || result.llmQuota) && (
                  <div className="p-6 glass-card">
                    <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4">LLM Quota</h3>
                    <div className="space-y-2 text-xs">
                      {result.llmUsage && (
                        <div className="text-slate-600 dark:text-slate-300">
                          Request usage: in {result.llmUsage.input_tokens}, out {result.llmUsage.output_tokens}, total {result.llmUsage.total_tokens}
                        </div>
                      )}
                      {result.llmQuota?.keys && Object.values(result.llmQuota.keys).slice(0, 3).map((key) => (
                        <div key={key.keyName} className="flex items-center justify-between rounded-lg bg-slate-100/60 dark:bg-dark-900/40 px-3 py-2">
                          <span className="font-semibold text-slate-500">{key.keyName}</span>
                          <span className="font-mono text-slate-700 dark:text-slate-300">{key.remainingTokens} left</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Deprecated APIs */}
                {result.deprecatedApis && result.deprecatedApis.length > 0 && (
                  <div className="p-6 glass-card border-l-4 border-amber-500">
                    <h3 className="text-md font-bold text-amber-700 dark:text-amber-400 mb-3 flex items-center gap-2">
                      <ShieldAlert size={16} /> Deprecated APIs Found
                    </h3>
                    <ul className="space-y-1.5">
                      {result.deprecatedApis.map((api, idx) => (
                        <li key={idx} className="text-[10px] text-amber-700 dark:text-amber-300 bg-amber-500/5 rounded-lg px-3 py-2 font-mono leading-relaxed">
                          ⚠ {api}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-6 glass-card">
                  <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4">Core Dependencies</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.dependencies.length > 0 ? (
                      result.dependencies.map((dep, idx) => (
                        <span key={idx} className="px-2.5 py-1 bg-slate-100 dark:bg-dark-800 rounded-lg text-[10px] font-semibold text-slate-600 dark:text-slate-400">
                          {dep}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-400 italic">No standard frameworks detected</span>
                    )}
                  </div>
                </div>
              </div>

              {/* RAG Recommendations */}
              <div className="lg:col-span-2 space-y-6">
                <div className="p-6 glass-card">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <BookOpen className="text-indigo-500" size={18} />
                      AI Recommendation & Reasoning
                    </h3>
                    <div className="flex items-center gap-3">
                      {result.usedProvider && result.usedProvider !== 'gemini' && (
                        <span className="px-3 py-1 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[10px] font-bold rounded-full border border-amber-500/20 uppercase tracking-wider">
                          Fallback: {result.usedProvider}
                        </span>
                      )}
                      <span className="px-3 py-1 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 text-xs font-bold rounded-full border border-indigo-500/20">
                        {result.migrationRecommendation}
                      </span>
                    </div>
                  </div>
                  
                  {/* Markdown or Pre-formatted text for AI output */}
                  <div className="prose dark:prose-invert max-w-none text-sm text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-dark-950/30 p-5 rounded-2xl border border-slate-200/30 dark:border-dark-900/30 whitespace-pre-wrap font-sans">
                    {result.reasoning}
                  </div>

                  {result.migrationRecommendation !== 'This project is already using the latest Java version. No migration is required.' && (
                    <div className="mt-6 flex justify-end">
                      <button
                        onClick={() => setActiveTab('migration')}
                        className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs transition-all shadow-md"
                      >
                        Proceed to Migration Center <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
