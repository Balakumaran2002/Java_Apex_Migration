import React from 'react';
import { Activity, CheckCircle, XCircle, Clock, PlayCircle, Loader2 } from 'lucide-react';

const StatusBadge = ({ status }) => {
  if (status === 'SUCCESS') {
    return (
      <div className="flex items-center space-x-1.5 text-green-400 bg-green-400/10 px-2.5 py-1 rounded-full border border-green-400/20 shadow-[0_0_10px_rgba(74,222,128,0.2)]">
        <CheckCircle size={14} />
        <span className="text-xs font-semibold tracking-wide">SUCCESS</span>
      </div>
    );
  }
  if (status === 'FAILED') {
    return (
      <div className="flex items-center space-x-1.5 text-red-400 bg-red-400/10 px-2.5 py-1 rounded-full border border-red-400/20 shadow-[0_0_10px_rgba(248,113,113,0.2)]">
        <XCircle size={14} />
        <span className="text-xs font-semibold tracking-wide">FAILED</span>
      </div>
    );
  }
  if (status === 'Pending' || status === 'RUNNING') {
    return (
      <div className="flex items-center space-x-1.5 text-blue-400 bg-blue-400/10 px-2.5 py-1 rounded-full border border-blue-400/20 shadow-[0_0_10px_rgba(96,165,250,0.2)]">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs font-semibold tracking-wide uppercase">{status}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center space-x-1.5 text-gray-400 bg-gray-400/10 px-2.5 py-1 rounded-full border border-gray-400/20">
      <span className="text-xs font-semibold tracking-wide uppercase">{status || 'Not Started'}</span>
    </div>
  );
};

export default function ExecutionComparison({ originalStatus, migratedStatus }) {
  const renderCard = (title, data) => (
    <div className="flex-1 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl relative overflow-hidden group hover:border-indigo-500/50 transition-all duration-300">
      {/* Decorative gradient orb */}
      <div className="absolute -top-20 -right-20 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl group-hover:bg-indigo-500/30 transition-all duration-500"></div>

      <div className="flex items-center space-x-3 mb-6">
        <div className="p-2.5 bg-indigo-500/20 rounded-xl border border-indigo-500/30">
          <Activity className="text-indigo-400" size={20} />
        </div>
        <h3 className="text-lg font-semibold text-white tracking-wide">{title}</h3>
      </div>

      <div className="space-y-4">
        {/* Metric Row */}
        <div className="flex items-center justify-between p-3 bg-black/20 rounded-xl border border-white/5 hover:bg-black/30 transition-colors">
          <div className="flex items-center space-x-2 text-gray-400">
            <span className="font-medium">Build Status</span>
          </div>
          <StatusBadge status={data?.buildStatus} />
        </div>

        {/* Metric Row */}
        <div className="flex items-center justify-between p-3 bg-black/20 rounded-xl border border-white/5 hover:bg-black/30 transition-colors">
          <div className="flex items-center space-x-2 text-gray-400">
            <span className="font-medium">Startup Status</span>
          </div>
          <StatusBadge status={data?.startupStatus} />
        </div>

        {/* Metric Row */}
        <div className="flex items-center justify-between p-3 bg-black/20 rounded-xl border border-white/5 hover:bg-black/30 transition-colors">
          <div className="flex items-center space-x-2 text-gray-400">
            <span className="font-medium">Test Status</span>
          </div>
          <StatusBadge status={data?.testStatus} />
        </div>

        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="p-3 bg-black/20 rounded-xl border border-white/5 text-center">
            <div className="text-2xl font-bold text-green-400">{data?.testsPassed || 0}</div>
            <div className="text-xs text-gray-500 mt-1 uppercase tracking-wider font-semibold">Tests Passed</div>
          </div>
          <div className="p-3 bg-black/20 rounded-xl border border-white/5 text-center">
            <div className="text-2xl font-bold text-red-400">{data?.testsFailed || 0}</div>
            <div className="text-xs text-gray-500 mt-1 uppercase tracking-wider font-semibold">Tests Failed</div>
          </div>
        </div>

        <div className="flex items-center justify-between p-3 bg-black/20 rounded-xl border border-white/5 mt-3">
          <div className="flex items-center space-x-2 text-gray-400">
            <Clock size={16} />
            <span className="font-medium text-sm">Execution Time</span>
          </div>
          <span className="text-white font-mono font-medium">{data?.executionTime || '0s'}</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-center space-x-3 mb-8">
          <PlayCircle className="text-indigo-400" size={28} />
          <h2 className="text-2xl font-bold text-white tracking-tight">Execution Comparison</h2>
        </div>
        
        <div className="flex flex-col md:flex-row gap-8">
          {renderCard('Original Repository', originalStatus)}
          {renderCard('Migrated Repository', migratedStatus)}
        </div>
      </div>
    </div>
  );
}
