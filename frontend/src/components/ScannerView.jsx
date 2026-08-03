import React, { useState, useEffect } from 'react';
import { FileCode, FunctionSquare, Network, Link, Maximize2, X, Download } from 'lucide-react';

export default function ScannerView({ repo, metrics }) {
  const [isGraphMaximized, setIsGraphMaximized] = useState(false);
  const [repoStructure, setRepoStructure] = useState("Waiting for scan data...");
  
  useEffect(() => {
    if (metrics.files_scanned === 0) {
      setRepoStructure("Waiting for scan data...");
      return;
    }

    // Attempt to fetch repo structure periodically if it says waiting
    const interval = setInterval(() => {
      fetch(`http://localhost:8000/api/repo-structure?repo=${encodeURIComponent(repo)}`)
        .then(res => res.json())
        .then(data => {
          if (data.content && data.content !== repoStructure) {
            setRepoStructure(data.content);
          }
        })
        .catch(err => console.error(err));
    }, 2000);
    return () => clearInterval(interval);
  }, [repo, repoStructure, metrics.files_scanned]);
  
  // Get owner and repo name to construct path. If invalid, just fallback.
  const repoName = repo.split('/')[1] || "LibraryManagementSystem";
  const graphUrl = `http://localhost:8000/api/graph?repo=${encodeURIComponent(repo)}`;

  return (
    <>
      <div className="grid-cols-4">
        <div className="card metric-card metric-blue">
          <div className="metric-header"><FileCode size={14} /> FILES SCANNED</div>
          <div className="metric-value">{metrics.files_scanned}</div>
        </div>
        <div className="card metric-card metric-green">
          <div className="metric-header"><FunctionSquare size={14} /> FUNCTIONS FOUND</div>
          <div className="metric-value">{metrics.functions_found}</div>
        </div>
        <div className="card metric-card metric-orange">
          <div className="metric-header"><Network size={14} /> GRAPH NODES</div>
          <div className="metric-value">{metrics.graph_nodes}</div>
        </div>
        <div className="card metric-card metric-blue">
          <div className="metric-header"><Link size={14} /> GRAPH EDGES</div>
          <div className="metric-value">{metrics.graph_edges}</div>
        </div>
      </div>
      
      <div className="card metric-card metric-red" style={{ marginBottom: '1.25rem', alignItems: 'flex-start' }}>
        <div className="metric-header" style={{ width: '100%', display: 'flex', justifyContent: 'space-between' }}>
          <span>SECURITY VULNERABILITIES</span>
          <button className="btn-primary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.7rem' }} onClick={() => window.location.href = `http://localhost:8000/api/download-security-report?repo=${encodeURIComponent(repo)}`}>
            <Download size={12} /> Download Report
          </button>
        </div>
        <div className="metric-value" style={{ fontSize: '1.5rem' }}>{metrics.security_vulns}</div>
      </div>

      <div className="grid-cols-2">
        <div className="card pane">
          <div className="pane-header">REPOSITORY STRUCTURE</div>
          <div className="pane-content" style={{ display: 'block', padding: '1rem', overflow: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.75rem', textAlign: 'left', background: 'rgba(0,0,0,0.1)' }}>
            {repoStructure}
          </div>
        </div>
        <div className="card pane">
          <div className="pane-header">
            AST KNOWLEDGE GRAPH
            <button className="btn-icon" onClick={() => setIsGraphMaximized(true)}>
              <Maximize2 size={16} />
            </button>
          </div>
          <div className="pane-content" style={{ padding: 0 }}>
            {metrics.graph_nodes > 0 ? (
              <iframe src={graphUrl} className="graph-iframe" title="AST Graph" />
            ) : (
              <div style={{ padding: '2rem' }}>Waiting for kb.json...</div>
            )}
          </div>
        </div>
      </div>

      {isGraphMaximized && (
        <div className="fullscreen-modal">
          <div className="modal-header">
            <div className="header-title">AST KNOWLEDGE GRAPH</div>
            <button className="btn-icon" onClick={() => setIsGraphMaximized(false)}>
              <X size={24} />
            </button>
          </div>
          <div style={{ flex: 1 }}>
            <iframe src={graphUrl} className="graph-iframe" title="AST Graph Fullscreen" />
          </div>
        </div>
      )}
    </>
  );
}
