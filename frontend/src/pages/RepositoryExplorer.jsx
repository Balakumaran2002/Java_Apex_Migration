import React, { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, ChevronDown, CheckCircle, Code, Play, LayoutList, Terminal } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ExecutionConsole from '../components/ExecutionConsole';
import ExecutionComparison from '../components/ExecutionComparison';

const FileTreeNode = ({ node, onSelect, selectedPath }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isFolder = node.type === 'folder';
  const isSelected = selectedPath === node.path;

  const handleClick = () => {
    if (isFolder) {
      setIsOpen(!isOpen);
    } else {
      onSelect(node.path);
    }
  };

  return (
    <div className="select-none">
      <div 
        className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded-md transition-colors ${
          isSelected ? 'bg-indigo-600/20 text-indigo-400' : 'hover:bg-slate-800 text-slate-300 hover:text-white'
        }`}
        onClick={handleClick}
      >
        <div className="flex items-center justify-center w-4 h-4 opacity-70">
          {isFolder ? (
            isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-slate-600"></span>
          )}
        </div>
        {isFolder ? <Folder size={16} className="text-blue-400" /> : <File size={16} className="text-slate-400" />}
        <span className="text-sm truncate">{node.name}</span>
      </div>
      
      {isFolder && isOpen && node.children && (
        <div className="ml-4 pl-2 border-l border-slate-800">
          {node.children.map((child, index) => (
            <FileTreeNode 
              key={`${child.path}-${index}`} 
              node={child} 
              onSelect={onSelect} 
              selectedPath={selectedPath} 
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default function RepositoryExplorer({ analysisResult }) {
  const [treeData, setTreeData] = useState(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [oldContent, setOldContent] = useState('');
  const [newContent, setNewContent] = useState('');
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState(null);

  // Resizable Sidebar State
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = React.useRef(null);

  const startResizing = (mouseDownEvent) => {
    mouseDownEvent.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    const handleMouseMove = (mouseMoveEvent) => {
      if (!isResizing || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = mouseMoveEvent.clientX - containerRect.left;
      if (newWidth >= 160 && newWidth <= 600) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  // Execution State
  const [showComparison, setShowComparison] = useState(false);
  const [showConsole, setShowConsole] = useState(false);
  const [consoleVersion, setConsoleVersion] = useState(null);
  const [originalStatus, setOriginalStatus] = useState(null);
  const [migratedStatus, setMigratedStatus] = useState(null);

  // Extract repo name
  let repoName = '';
  if (analysisResult && analysisResult.repoUrl) {
    repoName = analysisResult.repoUrl.split('/').pop().replace('.git', '');
  }

  useEffect(() => {
    if (repoName) {
      fetchTree();
    }
  }, [repoName]);

  const fetchTree = async () => {
    setLoadingTree(true);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/api/repository/${repoName}/tree`);
      if (!response.ok) throw new Error('Failed to fetch repository structure');
      const data = await response.json();
      setTreeData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingTree(false);
    }
  };

  const fetchFile = async (path) => {
    setSelectedFile(path);
    setLoadingFile(true);
    setOldContent('');
    setNewContent('');
    try {
      // Fetch new (migrated) file
      const resNew = await fetch(`http://localhost:8000/api/repository/${repoName}/file?file_path=${encodeURIComponent(path)}&version=new`);
      const dataNew = await resNew.json();
      setNewContent(dataNew.content || '');

      // Fetch old (original) file
      const resOld = await fetch(`http://localhost:8000/api/repository/${repoName}/file?file_path=${encodeURIComponent(path)}&version=old`);
      const dataOld = await resOld.json();
      setOldContent(dataOld.content || '');
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingFile(false);
    }
  };

  const getLanguage = (filename) => {
    if (!filename) return 'text';
    const ext = filename.split('.').pop().toLowerCase();
    const map = {
      java: 'java',
      xml: 'xml',
      properties: 'properties',
      yml: 'yaml',
      yaml: 'yaml',
      json: 'json',
      md: 'markdown',
      js: 'javascript',
      jsx: 'jsx'
    };
    return map[ext] || 'text';
  };

  const runExecution = async (version) => {
    try {
      if (version === 'original') {
        setOriginalStatus({ buildStatus: 'RUNNING', startupStatus: 'Pending', testStatus: 'Pending' });
      } else {
        setMigratedStatus({ buildStatus: 'RUNNING', startupStatus: 'Pending', testStatus: 'Pending' });
      }
      
      setConsoleVersion(version);
      setShowConsole(true);
      setShowComparison(false); // Switch to code view usually, but keep toolbar

      const res = await fetch(`http://localhost:8000/api/repository/${repoName}/run/${version}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to start execution');
      
      // Start polling status
      const pollInterval = setInterval(async () => {
        const statusRes = await fetch(`http://localhost:8000/api/repository/${repoName}/execution-status/${version}`);
        if (statusRes.ok) {
          const data = await statusRes.json();
          if (version === 'original') setOriginalStatus(data);
          else setMigratedStatus(data);

          if (data.buildStatus !== 'RUNNING' && data.buildStatus !== 'Pending' &&
              data.startupStatus !== 'Pending' && data.testStatus !== 'Pending') {
            clearInterval(pollInterval);
          }
        }
      }, 2000);

    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenConsole = () => {
    setConsoleVersion(consoleVersion || 'migrated');
    setShowConsole(true);
  };

  if (!repoName) {
    return (
      <div className="flex flex-col items-center justify-center h-[70vh] text-center px-4">
        <div className="w-20 h-20 rounded-full bg-slate-800/50 flex items-center justify-center mb-6">
          <Folder size={32} className="text-slate-500" />
        </div>
        <h2 className="text-2xl font-semibold mb-2">No Repository Found</h2>
        <p className="text-slate-400 max-w-md">
          Please run a Repository Analysis first so we know which repository to explore.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] animate-fade-in -mx-2 sm:-mx-6 lg:-mx-8 px-2 sm:px-6 lg:px-8 mt-2 relative">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
            Repository Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Explore files in <span className="text-white font-medium">{repoName}</span> and compare pre-migration and post-migration states.
          </p>
        </div>
        
        {/* Execution Toolbar */}
        <div className="flex items-center space-x-3 bg-slate-800/50 p-1.5 rounded-lg border border-slate-700/50 backdrop-blur-sm shadow-xl">
          <button 
            onClick={() => runExecution('original')}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium rounded-md transition-colors"
          >
            <Play size={14} className="text-blue-400" />
            <span>Run Original</span>
          </button>
          
          <button 
            onClick={() => runExecution('migrated')}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-md transition-colors shadow-[0_0_15px_rgba(79,70,229,0.3)]"
          >
            <Play size={14} className="text-green-400" />
            <span>Run Migrated</span>
          </button>
          
          <div className="w-px h-6 bg-slate-600 mx-1"></div>
          
          <button 
            onClick={() => setShowComparison(!showComparison)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${showComparison ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'hover:bg-slate-700 text-slate-300'}`}
          >
            <LayoutList size={14} />
            <span>Compare Results</span>
          </button>
          
          <button 
            onClick={handleOpenConsole}
            className={`flex items-center space-x-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${showConsole ? 'bg-slate-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`}
          >
            <Terminal size={14} />
            <span>Logs</span>
          </button>
        </div>
      </div>

      <div 
        ref={containerRef} 
        className="flex flex-1 overflow-hidden border border-slate-800 rounded-xl bg-slate-900/50 backdrop-blur-xl mb-4 relative"
      >
        
        {showComparison ? (
          <div className="flex-1 overflow-y-auto">
            <ExecutionComparison 
              originalStatus={originalStatus} 
              migratedStatus={migratedStatus} 
            />
          </div>
        ) : (
          <>
            {/* Left Pane: File Tree */}
            <div 
              style={{ width: `${sidebarWidth}px` }} 
              className="flex-shrink-0 flex flex-col bg-slate-900/80"
            >
              <div className="p-3 border-b border-slate-800 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Project Files</span>
                {loadingTree && <span className="w-3 h-3 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>}
              </div>
              <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
                {error ? (
                  <div className="p-4 text-sm text-red-400 text-center">{error}</div>
                ) : treeData && treeData.children ? (
                  treeData.children.map((child, idx) => (
                    <FileTreeNode key={idx} node={child} onSelect={fetchFile} selectedPath={selectedFile} />
                  ))
                ) : (
                  !loadingTree && <div className="p-4 text-sm text-slate-500 text-center">No files found</div>
                )}
              </div>
            </div>

            {/* Resize Handle */}
            <div 
              onMouseDown={startResizing}
              className="w-1.5 cursor-col-resize hover:bg-indigo-500/50 bg-slate-800/80 flex-shrink-0 transition-colors duration-150 relative group"
            >
              <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 group-hover:bg-indigo-500 bg-transparent transition-colors"></div>
            </div>

            {/* Right Pane: Split Screen Code Viewer */}
            <div className="flex-1 flex flex-col min-w-0 bg-[#0d1117]">
              {selectedFile ? (
                <div className="flex flex-col h-full">
                  <div className="flex items-center px-4 py-2 border-b border-slate-800 bg-slate-900/80">
                    <Code size={16} className="text-indigo-400 mr-2" />
                    <span className="text-sm font-medium text-slate-200 truncate">{selectedFile}</span>
                  </div>
                  
                  <div className="flex flex-1 overflow-hidden">
                    {/* Original Code */}
                    <div className="flex-1 border-r border-slate-800 flex flex-col min-w-0">
                      <div className="px-3 py-1.5 bg-slate-800/30 text-xs font-medium text-slate-400 border-b border-slate-800/50 flex justify-between items-center">
                        <span>Original Code</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-500">HEAD</span>
                      </div>
                      <div className="flex-1 overflow-auto bg-[#0d1117]">
                        {loadingFile ? (
                          <div className="flex justify-center items-center h-full">
                            <span className="w-6 h-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>
                          </div>
                        ) : (
                          <SyntaxHighlighter
                            language={getLanguage(selectedFile)}
                            style={vscDarkPlus}
                            customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
                            showLineNumbers={true}
                            wrapLines={false}
                          >
                            {oldContent}
                          </SyntaxHighlighter>
                        )}
                      </div>
                    </div>

                    {/* Migrated Code */}
                    <div className="flex-1 flex flex-col min-w-0">
                      <div className="px-3 py-1.5 bg-indigo-900/10 text-xs font-medium text-indigo-300 border-b border-slate-800/50 flex justify-between items-center">
                        <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-green-500" /> Migrated Code</span>
                        <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-[10px] text-indigo-300">Current</span>
                      </div>
                      <div className="flex-1 overflow-auto bg-[#0d1117]">
                        {loadingFile ? (
                          <div className="flex justify-center items-center h-full">
                            <span className="w-6 h-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>
                          </div>
                        ) : (
                          <SyntaxHighlighter
                            language={getLanguage(selectedFile)}
                            style={vscDarkPlus}
                            customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '13px' }}
                            showLineNumbers={true}
                            wrapLines={false}
                          >
                            {newContent}
                          </SyntaxHighlighter>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-slate-500">
                  <Code size={48} className="mb-4 opacity-20" />
                  <p>Select a file from the tree to view its contents.</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <ExecutionConsole 
        repoName={repoName} 
        version={consoleVersion} 
        isOpen={showConsole} 
        onClose={() => setShowConsole(false)} 
      />
    </div>
  );
}
