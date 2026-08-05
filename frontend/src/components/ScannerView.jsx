import React, { useState, useEffect } from 'react';
import { 
  Folder, Code, Code2, Box, Network, Link, 
  Maximize2, X, Copy, FileText, ChevronRight, ChevronDown
} from 'lucide-react';

export default function ScannerView({ repo, metrics, currentStep }) {
  const [isGraphMaximized, setIsGraphMaximized] = useState(false);
  const [repoStructure, setRepoStructure] = useState("");
  const [collapsedFolders, setCollapsedFolders] = useState({});

  const hasScannedData = metrics && (metrics.files_scanned > 0 || metrics.graph_nodes > 0);

  const repoName = repo 
    ? (repo.includes('/') ? repo.split('/')[1] : repo) 
    : (hasScannedData && metrics.repo_name ? metrics.repo_name : "—");

  const commitId = (hasScannedData && metrics.commit_id) ? metrics.commit_id : "—";
  const branch = (hasScannedData && metrics.branch) ? metrics.branch : "—";
  const lastUpdated = (hasScannedData && metrics.last_updated) ? metrics.last_updated : "—";

  useEffect(() => {
    if (!repo && !hasScannedData) {
      setRepoStructure("");
      return;
    }
    fetch(`http://localhost:8000/api/repo-structure?repo=${encodeURIComponent(repo)}`)
      .then(res => res.json())
      .then(data => {
        if (data.content && data.content !== "Waiting for scan data...") {
          setRepoStructure(data.content);
        } else {
          setRepoStructure("");
        }
      })
      .catch(err => console.error(err));
  }, [repo, metrics.files_scanned, metrics.graph_nodes, hasScannedData]);

  const graphUrl = `http://localhost:8000/api/graph?repo=${encodeURIComponent(repo)}`;

  // Metric values - display dynamic counts from kb.json / SSE metrics
  const displayFiles = metrics.files_scanned ? metrics.files_scanned.toLocaleString() : "0";
  const displayLines = metrics.lines_analyzed ? metrics.lines_analyzed.toLocaleString() : "0";
  const displayFunctions = metrics.functions_found ? metrics.functions_found.toLocaleString() : "0";
  const displayClasses = metrics.classes ? metrics.classes.toLocaleString() : "0";
  const displayNodes = metrics.graph_nodes ? metrics.graph_nodes.toLocaleString() : "0";
  const displayEdges = metrics.graph_edges ? metrics.graph_edges.toLocaleString() : "0";

  // Dynamic Languages Pie Chart Segments
  const hasLanguages = hasScannedData && metrics.languages && Object.keys(metrics.languages).length > 0;
  const langData = hasLanguages ? metrics.languages : {};

  const langColors = ['#FF4D6D', '#10B981', '#F59E0B', '#8B5CF6', '#3B82F6'];
  const langKeys = Object.keys(langData);

  let accumulatedPct = 0;
  const CIRCUMFERENCE = 87.96; // 2 * PI * 14
  const strokeSegments = langKeys.map((key, index) => {
    const pct = langData[key];
    const segmentLength = (pct / 100) * CIRCUMFERENCE;
    const strokeDasharray = `${segmentLength} ${CIRCUMFERENCE - segmentLength}`;
    const strokeDashoffset = `-${(accumulatedPct / 100) * CIRCUMFERENCE}`;
    accumulatedPct += pct;
    return { 
      key, 
      pct, 
      color: langColors[index % langColors.length], 
      strokeDasharray, 
      strokeDashoffset 
    };
  });

  // Helper to parse repo_structure.txt into formatted tree rows with icons
  const renderTreeLines = (rawText) => {
    if (!rawText) return null;
    const lines = rawText.split('\n');
    const contentLines = lines.filter(l => !l.startsWith('Repository Structure:') && !l.startsWith('==='));

    return contentLines.map((line, idx) => {
      if (!line.trim()) return null;
      
      const isFolder = line.trim().endsWith('/');
      const isMainGroup = line.includes('src/') || line.includes('controller/') || line.includes('service/') || line.includes('repository/') || line.includes('frontend/') || line.includes('.github/');
      const name = line.replace(/^[│├└──\s]+/, '').trim();
      const prefix = line.match(/^[│├└──\s]+/)?.[0] || '';

      return (
        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', lineHeight: '1.6', fontSize: '0.78rem' }}>
          <span style={{ color: '#CBD5E1', fontFamily: 'monospace' }}>{prefix}</span>
          {isFolder ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontWeight: isMainGroup ? 700 : 600, color: '#1E293B' }}>
              <Folder size={14} color={isMainGroup ? "#F59E0B" : "#FF4D6D"} fill={isMainGroup ? "#F59E0B" : "#FFD1D9"} />
              {name}
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#475569' }}>
              <FileText size={13} color="#FF4D6D" />
              {name}
            </span>
          )}
        </div>
      );
    });
  };

  return (
    <>
      {/* 6 Summary Metric Cards Bar */}
      <div className="grid-cols-6">
        <div className="pastel-card card-mint">
          <div className="summary-card-header"><Folder size={14} /> Repository Files</div>
          <div className="summary-card-value">{displayFiles}</div>
        </div>

        <div className="pastel-card card-cyan">
          <div className="summary-card-header"><Code size={14} /> Lines Analyzed</div>
          <div className="summary-card-value">{displayLines}</div>
        </div>

        <div className="pastel-card card-peach">
          <div className="summary-card-header"><Code2 size={14} /> Functions Scanned</div>
          <div className="summary-card-value">{displayFunctions}</div>
        </div>

        <div className="pastel-card card-purple">
          <div className="summary-card-header"><Box size={14} /> Classes</div>
          <div className="summary-card-value">{displayClasses}</div>
        </div>

        <div className="pastel-card card-green">
          <div className="summary-card-header"><Network size={14} /> Graph Nodes</div>
          <div className="summary-card-value">{displayNodes}</div>
        </div>

        <div className="pastel-card card-pink">
          <div className="summary-card-header"><Link size={14} /> Graph Edges</div>
          <div className="summary-card-value">{displayEdges}</div>
        </div>
      </div>

      {/* 3-Column Dashboard Pane */}
      <div className="grid-cols-3-dash">
        
        {/* Column 1: Repository Overview */}
        <div className="card pane">
          <div className="pane-title-bar">
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ color: '#FF4D6D' }}>🐙</span> Repository Overview
            </span>
            <button className="btn-icon" title="Copy Details"><Copy size={14} /></button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Repo Name:</span>
              <span style={{ fontWeight: 600, color: '#0F172A' }}>{repoName}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Branch:</span>
              <span style={{ fontWeight: 600, color: '#0F172A' }}>{branch}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Commit ID:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#0F172A' }}>{commitId}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>Last Updated:</span>
              <span style={{ fontWeight: 600, fontSize: '0.75rem', color: '#334155' }}>
                {lastUpdated}
              </span>
            </div>
          </div>

          <div style={{ marginTop: '1rem', borderTop: '1px solid #E2E8F0', paddingTop: '1rem' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.75rem' }}>Languages</div>
            
            {hasLanguages ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                {/* Dynamic SVG Donut / Pie Chart */}
                <svg width="100" height="100" viewBox="0 0 36 36" style={{ transform: 'rotate(-90deg)' }}>
                  <circle cx="18" cy="18" r="14" fill="none" stroke="#E2E8F0" strokeWidth="6" />
                  {strokeSegments.map(seg => (
                    <circle
                      key={seg.key}
                      cx="18"
                      cy="18"
                      r="14"
                      fill="none"
                      stroke={seg.color}
                      strokeWidth="6"
                      strokeDasharray={seg.strokeDasharray}
                      strokeDashoffset={seg.strokeDashoffset}
                    />
                  ))}
                </svg>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.75rem', flex: 1, marginLeft: '1rem' }}>
                  {strokeSegments.map(seg => (
                    <div key={seg.key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span><span style={{ color: seg.color, fontWeight: 900 }}>●</span> {seg.key}</span>
                      <span style={{ fontWeight: 700 }}>{seg.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontStyle: 'italic', textAlign: 'center', padding: '1.5rem 0' }}>
                No language data analyzed yet.
              </div>
            )}
          </div>
        </div>

        {/* Column 2: Strategy to Generate Test Cases (Knowledge Graph) */}
        <div className="card pane" style={{ flex: 1 }}>
          <div className="pane-title-bar">
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ color: '#FF4D6D' }}>🕸️</span> Strategy to Generate Test Cases (Knowledge Graph)
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="badge-counter">Nodes: <b>{metrics.graph_nodes || 0}</b> | Edges: <b>{metrics.graph_edges || 0}</b></span>
              <button className="btn-icon" onClick={() => setIsGraphMaximized(true)} title="Maximize Graph">
                <Maximize2 size={15} />
              </button>
            </div>
          </div>

          <div style={{ 
            flex: 1, 
            height: '380px',
            minHeight: '380px', 
            background: '#FAFAFA', 
            borderRadius: '0.75rem', 
            border: '1px solid #E2E8F0', 
            overflow: 'hidden', 
            position: 'relative' 
          }}>
            {hasScannedData ? (
              <iframe 
                src={graphUrl} 
                title="AST Knowledge Graph" 
                style={{ width: '100%', height: '100%', minHeight: '380px', border: 'none', display: 'block' }}
              />
            ) : (
              <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center', color: '#94A3B8' }}>
                <span style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🕸️</span>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#64748B' }}>Knowledge Graph Ready</span>
                <span style={{ fontSize: '0.75rem', marginTop: '0.25rem', maxWidth: '280px' }}>
                  Enter a GitHub repository URL above and click <b>Run Pipeline</b> to build the AST Knowledge Graph.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Column 3: Repository Structure */}
        <div className="card pane">
          <div className="pane-title-bar">
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              📁 Repository Structure
            </span>
          </div>

          <div style={{ 
            flex: 1, 
            height: '380px', 
            maxHeight: '380px',
            background: '#FFFFFF', 
            borderRadius: '0.75rem', 
            border: '1px solid #E2E8F0', 
            padding: '0.85rem', 
            fontSize: '0.78rem', 
            overflowY: 'auto',
            overflowX: 'auto'
          }}>
            {hasScannedData && repoStructure ? (
              <div>
                {renderTreeLines(repoStructure)}
              </div>
            ) : (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', fontSize: '0.75rem', fontStyle: 'italic' }}>
                Waiting for scan data...
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Fullscreen Graph Modal */}
      {isGraphMaximized && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          backgroundColor: 'rgba(15, 23, 42, 0.94)',
          backdropFilter: 'blur(8px)',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          padding: '1.25rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', color: '#FFFFFF' }}>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ color: '#FF4D6D' }}>🕸️</span> Strategy to Generate Test Cases (AST Knowledge Graph)
            </div>
            <button 
              onClick={() => setIsGraphMaximized(false)} 
              style={{ background: 'none', border: 'none', color: '#FFFFFF', cursor: 'pointer', padding: '0.4rem', borderRadius: '0.35rem' }}
              title="Close Fullscreen"
            >
              <X size={26} />
            </button>
          </div>
          <div style={{ flex: 1, borderRadius: '0.75rem', overflow: 'hidden', border: '1px solid #334155' }}>
            <iframe 
              src={graphUrl} 
              style={{ width: '100%', height: '100%', border: 'none' }} 
              title="AST Graph Fullscreen" 
            />
          </div>
        </div>
      )}
    </>
  );
}
