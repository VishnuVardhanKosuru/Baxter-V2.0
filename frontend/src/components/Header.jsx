import React from 'react';
import { Play, Zap, Sun, Moon } from 'lucide-react';

export default function Header({ repo, setRepo, onRun, isRunning, theme, onToggleTheme }) {
  return (
    <div className="header-bar">
      <div className="header-title">
        <div className="app-logo">
          <Zap size={18} color="white" fill="white" />
        </div>
        <div>
          <div className="app-name">Test Case Generator Agent</div>
          <div className="app-subtitle">AI-Powered Quality Assurance Pipeline</div>
        </div>
      </div>
      <div className="header-actions">
        <div className="repo-input">
          <input 
            type="text" 
            value={repo} 
            onChange={(e) => setRepo(e.target.value)} 
            placeholder="owner/repo" 
          />
        </div>
        <button className="btn-icon" onClick={onToggleTheme} title="Toggle Theme" style={{ padding: '0.5rem', background: 'var(--card-bg)', border: '1px solid var(--card-border)' }}>
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button className="btn-primary" onClick={onRun} disabled={isRunning}>
          <Play size={14} fill="currentColor" /> {isRunning ? "Running..." : "Run Pipeline"}
        </button>
      </div>
    </div>
  );
}
