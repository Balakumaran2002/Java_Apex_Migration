import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, X, Bot, Sparkles, AlertCircle, RefreshCw, Trash2, ArrowUpRight } from 'lucide-react';
import { askChatbot } from '../api';

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('chat_messages');
      return saved ? JSON.parse(saved) : [
        { id: 1, sender: 'bot', text: 'Hello! I am your AI Migration Assistant. I can help with Java 17/21 upgrades, Spring Boot 3 configurations, LLM migrations, or code conversion questions. How can I assist you today?' }
      ];
    } catch (e) {
      return [
        { id: 1, sender: 'bot', text: 'Hello! I am your AI Migration Assistant. I can help with Java 17/21 upgrades, Spring Boot 3 configurations, migration repairs, or code conversion questions. How can I assist you today?' }
      ];
    }
  });
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem('chat_messages', JSON.stringify(messages));
    } catch (e) {
      // Ignore storage errors
    }
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async (textToSend) => {
    const text = textToSend || inputValue.trim();
    if (!text) return;

    if (!textToSend) {
      setInputValue('');
    }

    const userMsg = { id: Date.now(), sender: 'user', text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const result = await askChatbot(text);
      if (result.errorMessage) {
        setMessages(prev => [
          ...prev,
          { id: Date.now() + 1, sender: 'bot', text: `Sorry, I encountered an error: ${result.errorMessage}`, isError: true }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          { id: Date.now() + 1, sender: 'bot', text: result.response }
        ]);
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { id: Date.now() + 1, sender: 'bot', text: 'Failed to communicate with the chatbot backend. Make sure the API key is configured and the backend server is running.', isError: true }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    const defaultMsg = [
      { id: 1, sender: 'bot', text: 'Hello! I am your AI Migration Assistant. I can help with Java 17/21 upgrades, Spring Boot 3 configurations, LLM migrations, or code conversion questions. How can I assist you today?' }
    ];
    setMessages(defaultMsg);
    localStorage.setItem('chat_messages', JSON.stringify(defaultMsg));
  };

  // Simple Markdown-like formatter for code blocks, bold text, and linebreaks
  const renderMessageContent = (text) => {
    if (!text) return null;

    // Split by code blocks ```
    const parts = text.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('```') && part.endsWith('```')) {
        // Code block
        const lines = part.slice(3, -3).trim().split('\n');
        let language = 'code';
        if (lines[0] && !lines[0].includes(' ') && lines[0].length < 10) {
          language = lines[0];
          lines.shift();
        }
        const codeContent = lines.join('\n');
        return (
          <div key={index} className="my-3 rounded-xl overflow-hidden border border-slate-200/20 dark:border-dark-800/80 bg-slate-950 text-slate-100 font-mono text-xs">
            <div className="bg-slate-900 px-3 py-1.5 border-b border-slate-800 text-[10px] text-slate-400 font-semibold flex justify-between items-center select-none">
              <span>{language.toUpperCase()}</span>
              <button 
                onClick={() => navigator.clipboard.writeText(codeContent)}
                className="hover:text-white transition-colors"
              >
                Copy
              </button>
            </div>
            <pre className="p-3 overflow-x-auto whitespace-pre leading-relaxed">{codeContent}</pre>
          </div>
        );
      } else {
        // Plain text with basic inline styling
        // Bold formatting
        const lines = part.split('\n').map((line, lIdx) => {
          const boldParts = line.split(/(\*\*.*?\*\*)/g);
          return (
            <span key={lIdx} className="block min-h-[6px]">
              {boldParts.map((bPart, bIdx) => {
                if (bPart.startsWith('**') && bPart.endsWith('**')) {
                  return <strong key={bIdx} className="font-extrabold text-slate-900 dark:text-white">{bPart.slice(2, -2)}</strong>;
                }
                return bPart;
              })}
            </span>
          );
        });
        return <div key={index} className="space-y-1">{lines}</div>;
      }
    });
  };

  const suggestions = [
    "How does the LLM migration work?",
    "How do I migrate to Java 21?",
    "How to fix Spring Boot 3 namespace errors?",
    "Show Java-to-Python conversion details"
  ];

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 p-4 bg-brand-600 hover:bg-brand-700 text-white rounded-full shadow-2xl transition-all hover:scale-110 active:scale-95 flex items-center justify-center z-40 group"
      >
        <div className="absolute inset-0 rounded-full bg-brand-500 opacity-20 group-hover:animate-ping"></div>
        {isOpen ? <X size={24} /> : <MessageSquare size={24} />}
      </button>

      {/* Chat Drawer Side Panel */}
      <div 
        className={`fixed inset-y-0 right-0 w-full max-w-md bg-white dark:bg-dark-900 border-l border-slate-200/50 dark:border-dark-800/40 shadow-2xl flex flex-col z-40 transition-all duration-300 transform ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b border-slate-200/50 dark:border-dark-800/40 flex items-center justify-between bg-slate-50/50 dark:bg-dark-950/20">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 text-indigo-500 rounded-xl">
              <Bot size={20} />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-1.5">
                AI Migration Chatbot
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </h3>
              <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-1">
                <Sparkles size={10} className="text-brand-500" /> RAG Knowledge Enabled
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={clearChat}
              title="Clear conversation"
              className="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 dark:hover:bg-rose-500/5 rounded-xl transition-all"
            >
              <Trash2 size={16} />
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-dark-800 rounded-xl transition-all"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Messages Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 max-w-[85%] ${
                msg.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
              }`}
            >
              {msg.sender === 'bot' && (
                <div className="h-8 w-8 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center flex-shrink-0 border border-brand-500/20">
                  <Bot size={16} />
                </div>
              )}
              
              <div className={`p-3.5 rounded-2xl text-xs leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-brand-600 text-white rounded-tr-none shadow-md'
                  : msg.isError
                    ? 'bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 rounded-tl-none flex gap-2 items-start'
                    : 'bg-slate-100/80 dark:bg-dark-800/40 border border-slate-200/30 dark:border-dark-800/30 text-slate-700 dark:text-slate-300 rounded-tl-none'
              }`}>
                {msg.isError && <AlertCircle size={14} className="flex-shrink-0 mt-0.5 text-rose-500" />}
                <div>{renderMessageContent(msg.text)}</div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 max-w-[85%] mr-auto items-center">
              <div className="h-8 w-8 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center flex-shrink-0 border border-brand-500/20">
                <Bot size={16} />
              </div>
              <div className="p-3 rounded-2xl bg-slate-100/50 dark:bg-dark-800/20 border border-slate-200/10 dark:border-dark-800/10 text-slate-400 text-xs flex items-center gap-2">
                <RefreshCw size={12} className="animate-spin" />
                Thinking...
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        {messages.length === 1 && !loading && (
          <div className="p-4 border-t border-slate-100 dark:border-dark-800/80 space-y-2">
            <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Suggested Questions</span>
            <div className="flex flex-col gap-1.5">
              {suggestions.map((sug, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(sug)}
                  className="flex items-center justify-between text-left px-3 py-2 rounded-xl bg-slate-50 hover:bg-brand-500/10 border border-slate-200/30 dark:border-dark-800/30 dark:bg-dark-950/20 text-slate-600 dark:text-slate-400 text-xs font-semibold transition-all group hover:text-brand-600 dark:hover:text-brand-400"
                >
                  {sug}
                  <ArrowUpRight size={12} className="text-slate-400 group-hover:text-brand-500 opacity-0 group-hover:opacity-100 transition-all" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Form */}
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          className="p-4 border-t border-slate-200/50 dark:border-dark-800/40 bg-slate-50/50 dark:bg-dark-950/20 flex gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a migration question..."
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-dark-800 bg-white/50 dark:bg-dark-950/50 focus:outline-none text-xs"
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="p-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center shadow-md shadow-brand-500/10"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </>
  );
}
