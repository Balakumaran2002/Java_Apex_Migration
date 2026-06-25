import React, { useEffect, useRef, useState } from 'react';
import { Download, Trash2, X } from 'lucide-react';

export default function ExecutionConsole({ repoName, version, isOpen, onClose }) {
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('Connecting...');
  const bottomRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !repoName || !version) return;

    setLogs([]);
    setStatus('Connecting to Execution Server...');
    
    // Connect to WebSocket
    const wsUrl = `ws://localhost:8000/api/ws/repository/${repoName}/logs/${version}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus(`Execution Server Connected (${version})`);
    };

    ws.onmessage = (event) => {
      setLogs((prev) => [...prev, event.data]);
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      setStatus('Connection Error. Make sure the execution has started.');
    };

    ws.onclose = () => {
      setStatus('Execution Finished / Disconnected.');
    };

    return () => {
      ws.close();
    };
  }, [repoName, version, isOpen]);

  useEffect(() => {
    // Auto-scroll to bottom
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleClear = () => {
    setLogs([]);
  };

  const handleDownload = () => {
    const blob = new Blob([logs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${repoName}_${version}_execution_logs.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex flex-col h-1/3 bg-gray-900 border-t border-gray-700 shadow-2xl rounded-t-xl overflow-hidden transition-transform duration-300 transform translate-y-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-3">
          <span className="font-mono text-sm font-semibold text-gray-300">
            &gt;_ Execution Console ({version === 'original' ? 'Original' : 'Migrated'})
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            status.includes('Connected') ? 'bg-green-500/20 text-green-400' :
            status.includes('Finished') ? 'bg-blue-500/20 text-blue-400' :
            'bg-yellow-500/20 text-yellow-400'
          }`}>
            {status}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <button onClick={handleDownload} className="p-1 text-gray-400 hover:text-white transition-colors" title="Download Logs">
            <Download size={16} />
          </button>
          <button onClick={handleClear} className="p-1 text-gray-400 hover:text-white transition-colors" title="Clear Console">
            <Trash2 size={16} />
          </button>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition-colors" title="Close Console">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div className="flex-1 overflow-y-auto p-4 bg-[#0d1117] font-mono text-sm">
        {logs.length === 0 ? (
          <div className="text-gray-500 italic">Waiting for logs...</div>
        ) : (
          logs.map((log, index) => {
            // Apply simple colors based on keywords
            let colorClass = 'text-gray-300';
            const logUpper = log.toUpperCase();
            if (logUpper.includes('ERROR') || logUpper.includes('FAILED') || logUpper.includes('EXCEPTION')) {
              colorClass = 'text-red-400';
            } else if (logUpper.includes('WARN')) {
              colorClass = 'text-yellow-400';
            } else if (logUpper.includes('SUCCESS') || logUpper.includes('STARTED')) {
              colorClass = 'text-green-400';
            } else if (logUpper.includes('INFO')) {
              colorClass = 'text-blue-300';
            }
            
            return (
              <div key={index} className={`${colorClass} whitespace-pre-wrap break-words`}>
                {log}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
