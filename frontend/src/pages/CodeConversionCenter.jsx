import React, { useState } from 'react';
import { Terminal, Play, Download, AlertTriangle, FileCode, CheckCircle, ChevronRight, FileText } from 'lucide-react';
import { convertCode, getPythonZipUrl, getConversionReportUrl } from '../api';

export default function CodeConversionCenter({ 
  setActiveTab,
  files,
  setFiles,
  activeFile,
  setActiveFile,
  loading,
  setLoading,
  result,
  setResult,
  error,
  setError,
  elapsedTime,
  timeTaken,
  setTimeTaken
}) {
  const [newFileName, setNewFileName] = useState('Untitled.java');
  const [newFileContent, setNewFileContent] = useState('');

  // File Upload handling
  const handleFileUpload = (e) => {
    const uploadedFiles = e.target.files;
    if (!uploadedFiles) return;

    const newFilesMap = { ...files };
    let firstAddedFile = '';

    Array.from(uploadedFiles).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        newFilesMap[file.name] = event.target.result;
        setFiles({ ...newFilesMap });
        if (!activeFile && !firstAddedFile) {
          setActiveFile(file.name);
        }
      };
      reader.readAsText(file);
    });
  };

  // Add paste code file
  const handleAddPasteFile = () => {
    if (!newFileContent.trim()) return;
    
    let name = newFileName.trim();
    if (!name.endsWith('.java')) {
      name += '.java';
    }

    const updated = {
      ...files,
      [name]: newFileContent
    };

    setFiles(updated);
    setActiveFile(name);
    setNewFileContent('');
    setNewFileName('Untitled.java');
  };

  const handleRemoveFile = (fileName) => {
    const updated = { ...files };
    delete updated[fileName];
    setFiles(updated);

    if (activeFile === fileName) {
      const remaining = Object.keys(updated);
      setActiveFile(remaining.length > 0 ? remaining[0] : '');
    }
  };

  const handleConvert = async () => {
    const fileKeys = Object.keys(files);
    if (fileKeys.length === 0) {
      setError("Please add at least one Java file to convert.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setTimeTaken(null);

    const startTime = Date.now();

    try {
      const data = await convertCode(files);
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      if (data.errorMessage) {
        setError(data.errorMessage);
      } else {
        setResult(data);
        setTimeTaken(duration);
        localStorage.setItem('last_conversion_time', JSON.stringify(duration));
        
        // Save to LocalStorage
        localStorage.setItem('last_conversion_input', JSON.stringify(files));
        localStorage.setItem('last_conversion', JSON.stringify(data));
        
        // Update statistics
        const stats = JSON.parse(localStorage.getItem('assistant_stats') || '{"reposAnalyzed":0,"migrationsRun":0,"filesConverted":0}');
        stats.filesConverted += fileKeys.length;
        localStorage.setItem('assistant_stats', JSON.stringify(stats));
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'An error occurred during code conversion.');
    } finally {
      setLoading(false);
    }
  };

  const fileKeys = Object.keys(files);
  const activePyFile = activeFile ? activeFile.replace('.java', '.py') : '';

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Configuration Frame */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left pane: File listing & Add paste */}
        <div className="lg:col-span-1 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <FileCode className="text-indigo-500" size={18} />
              Java Sources Listing
            </h3>

            {/* Upload form */}
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                Upload Java Files
              </label>
              <input
                type="file"
                multiple
                accept=".java"
                onChange={handleFileUpload}
                className="block w-full text-xs text-slate-500 dark:text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-500/10 file:text-brand-600 dark:file:text-brand-400 hover:file:bg-brand-500/20 cursor-pointer"
              />
            </div>

            {/* Paste box toggle or form */}
            <div className="border-t border-slate-100 dark:border-dark-800 pt-4 space-y-3">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Or Paste Code Snippet
              </label>
              <input
                type="text"
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                placeholder="ClassA.java"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-dark-800 bg-white/50 dark:bg-dark-950/50 focus:outline-none"
              />
              <textarea
                value={newFileContent}
                onChange={(e) => setNewFileContent(e.target.value)}
                placeholder="public class ClassA { ... }"
                rows={4}
                className="w-full p-3 text-xs font-mono rounded-lg border border-slate-200 dark:border-dark-800 bg-white/50 dark:bg-dark-950/50 focus:outline-none resize-none"
              />
              <button
                type="button"
                onClick={handleAddPasteFile}
                className="w-full py-2 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/30 dark:hover:bg-indigo-950/50 border border-indigo-200/50 dark:border-indigo-900/50 text-indigo-600 dark:text-indigo-400 font-semibold rounded-lg text-xs transition-all"
              >
                Add File to List
              </button>
            </div>
          </div>

          {/* Files collection */}
          <div className="p-6 glass-card">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Files to Convert ({fileKeys.length})</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {fileKeys.length > 0 ? (
                fileKeys.map((name) => (
                  <div
                    key={name}
                    onClick={() => setActiveFile(name)}
                    className={`flex justify-between items-center p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                      activeFile === name
                        ? 'border-brand-500/50 bg-brand-500/10 text-brand-700 dark:text-brand-400 font-semibold'
                        : 'border-slate-100 dark:border-dark-800/40 bg-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-100/30'
                    }`}
                  >
                    <span className="truncate flex items-center gap-2">📄 {name}</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveFile(name);
                      }}
                      className="text-rose-500 hover:text-rose-700 px-1 font-bold"
                    >
                      ×
                    </button>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-4">No files added yet</div>
              )}
            </div>

            {fileKeys.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={handleConvert}
                  disabled={loading}
                  className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs shadow-md transition-all font-sans"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Translating... ({elapsedTime}s)
                    </>
                  ) : (
                    <>
                      <Play size={14} /> Translate Code to Python
                    </>
                  )}
                </button>
                {timeTaken && result && !loading && (
                  <div className="mt-3 text-[11px] text-center text-emerald-600 dark:text-emerald-400 font-semibold flex items-center justify-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 py-2 rounded-xl">
                    <CheckCircle size={12} className="text-emerald-500" />
                    Converted in {timeTaken}s
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right pane: Side-by-side comparison editors */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Terminal className="text-indigo-500" size={18} />
              Side-by-Side Code Translation Viewer
            </h3>

            {activeFile ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Java Side */}
                <div className="flex flex-col border border-slate-200/50 dark:border-dark-800/80 rounded-xl overflow-hidden">
                  <div className="bg-slate-100 dark:bg-dark-900 px-4 py-2 border-b border-slate-200/50 dark:border-dark-800/80 flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Java Code</span>
                    <span className="text-[10px] font-mono bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded font-bold">{activeFile}</span>
                  </div>
                  <textarea
                    value={files[activeFile] || ''}
                    onChange={(e) => {
                      setFiles({
                        ...files,
                        [activeFile]: e.target.value
                      });
                    }}
                    rows={16}
                    className="p-4 bg-slate-950 text-slate-100 text-xs font-mono focus:outline-none resize-none leading-relaxed"
                  />
                </div>

                {/* Python Side */}
                <div className="flex flex-col border border-slate-200/50 dark:border-dark-800/80 rounded-xl overflow-hidden">
                  <div className="bg-slate-100 dark:bg-dark-900 px-4 py-2 border-b border-slate-200/50 dark:border-dark-800/80 flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Python Code</span>
                    <span className="text-[10px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded font-bold">{activePyFile}</span>
                  </div>
                  <pre className="p-4 bg-slate-950 text-emerald-400 text-xs font-mono h-[324px] overflow-y-auto overflow-x-auto leading-relaxed select-all">
                    {result?.convertedFiles?.[activePyFile] || '# Click Translate to generate Python code'}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-sm text-slate-400 dark:text-slate-500 italic text-center py-20 border-2 border-dashed border-slate-200 dark:border-dark-800 rounded-2xl bg-slate-50/50 dark:bg-dark-900/10">
                Create or paste a file, then click on the filename to inspect.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-400 glass-card flex gap-3 items-start animate-fadeIn">
          <AlertTriangle size={24} className="flex-shrink-0" />
          <div>
            <h4 className="font-bold text-sm">Conversion Error</h4>
            <p className="mt-1 text-xs leading-relaxed">{error}</p>
          </div>
        </div>
      )}

      {/* Analysis Output Section */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Detailed explanation and notes */}
          <div className="lg:col-span-2 space-y-6">
            <div className="p-6 glass-card">
              <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                <FileText className="text-indigo-500" size={18} />
                Mapping & Conversion Explanation
              </h3>
              <div className="prose dark:prose-invert max-w-none text-sm text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-dark-950/20 p-5 rounded-2xl border border-slate-200/30 dark:border-dark-900/30 whitespace-pre-wrap">
                {result.explanation}
              </div>
            </div>
          </div>

          {/* Warnings and Download section */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-6 glass-card border-amber-500/20">
              <h3 className="text-md font-bold text-amber-500 flex items-center gap-2 mb-4">
                <AlertTriangle size={18} />
                Unsupported Features & Warnings
              </h3>
              <div className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-amber-500/5 p-4 rounded-xl border border-amber-500/10 whitespace-pre-wrap">
                {result.warnings || 'No significant conversion warnings detected.'}
              </div>
            </div>

            <div className="p-6 glass-card space-y-3">
              <h3 className="text-md font-bold text-slate-900 dark:text-white mb-2">Transpilation Artifacts</h3>
              <a
                href={getPythonZipUrl()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
              >
                <Download size={14} /> Download Converted ZIP
              </a>
              <a
                href={getConversionReportUrl()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-dark-800 dark:hover:bg-dark-700 text-slate-800 dark:text-slate-200 font-semibold rounded-xl text-xs transition-all border border-slate-200/50 dark:border-dark-700"
              >
                <Download size={14} /> Download PDF Report
              </a>
              <button
                onClick={() => setActiveTab('conversionReport')}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
              >
                View Conversion Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
