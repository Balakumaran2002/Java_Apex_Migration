import React, { useState, useEffect } from 'react';
import { FileText, Download, AlertTriangle, CheckCircle } from 'lucide-react';
import { getConversionReportUrl, getPythonZipUrl } from '../api';

export default function ConversionReport() {
  const [conversion, setConversion] = useState(null);
  const [inputFiles, setInputFiles] = useState({});

  useEffect(() => {
    const lastConversion = JSON.parse(localStorage.getItem('last_conversion') || 'null');
    const lastInput = JSON.parse(localStorage.getItem('last_conversion_input') || '{}');
    setConversion(lastConversion);
    setInputFiles(lastInput);
  }, []);

  if (!conversion) {
    return (
      <div className="p-8 text-center glass-card animate-fadeIn">
        <FileText size={48} className="mx-auto text-slate-300 dark:text-slate-700 mb-4" />
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200 mb-2">No Conversion Report Available</h3>
        <p className="text-sm text-slate-400 max-w-sm mx-auto mb-6">
          You haven't translated any code files yet. Access the Code Conversion Center first.
        </p>
      </div>
    );
  }

  const javaFiles = Object.keys(inputFiles);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-6 glass-card bg-gradient-to-r from-slate-100 to-indigo-50/20 dark:from-dark-900 dark:to-dark-950/40">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <FileText className="text-indigo-500" size={22} />
            Java to Python Conversion Report
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Detailed translation audit, explanations, and unsupported feature warnings.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href={getPythonZipUrl()}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl text-xs transition-all shadow-sm"
          >
            <Download size={12} /> Download ZIP
          </a>
          <a
            href={getConversionReportUrl()}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-dark-800 dark:hover:bg-dark-700 text-slate-800 dark:text-slate-200 font-semibold rounded-xl text-xs transition-all border border-slate-200/50 dark:border-dark-700"
          >
            <Download size={12} /> Download PDF
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left pane: File listing */}
        <div className="lg:col-span-1 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4">Files Processed</h3>
            <table className="w-full text-xs text-left">
              <tbody>
                <tr className="border-b border-slate-100 dark:border-dark-800">
                  <td className="py-3 font-semibold text-slate-400">Total Java Files</td>
                  <td className="py-3 font-bold text-slate-800 dark:text-slate-200">{javaFiles.length}</td>
                </tr>
                <tr className="border-b border-slate-100 dark:border-dark-800">
                  <td className="py-3 font-semibold text-slate-400">Total Python Files</td>
                  <td className="py-3 font-bold text-emerald-600 dark:text-emerald-400">{Object.keys(conversion.convertedFiles).length}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="p-6 glass-card">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 font-bold">Converted Files Mapping</h3>
            <div className="space-y-2.5 max-h-60 overflow-y-auto">
              {javaFiles.map((name) => (
                <div key={name} className="text-xs font-mono text-slate-600 dark:text-slate-400">
                  📄 {name} ⟶ {name.replace('.java', '.py')}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right pane: Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 glass-card">
            <h3 className="text-md font-bold text-slate-900 dark:text-white mb-4">Structure Conversion Explanation</h3>
            <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-dark-950/20 p-5 rounded-2xl border border-slate-200/30 dark:border-dark-900/30 whitespace-pre-wrap">
              {conversion.explanation}
            </div>
          </div>

          <div className="p-6 glass-card border-amber-500/20">
            <h3 className="text-md font-bold text-amber-500 mb-4 flex items-center gap-2">
              <AlertTriangle size={18} /> Unsupported Features & Warnings
            </h3>
            <div className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-amber-500/5 p-4 rounded-xl border border-amber-500/10 whitespace-pre-wrap">
              {conversion.warnings || 'No warnings generated.'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
