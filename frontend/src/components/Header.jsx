import React from 'react';
import { Play, Zap } from 'lucide-react';

export default function Header({ repo, setRepo, onRun, isRunning }) {
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
        <button className="btn-primary" onClick={onRun} disabled={isRunning}>
          <Play size={14} fill="currentColor" /> {isRunning ? "Running..." : "Run Pipeline"}
        </button>
      </div>
    </div>
  );
}
