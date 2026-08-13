import React, { useState } from 'react';
import { JIRA_RELEASES_DATA } from '../data/jiraMockData';
import { 
  FileText, 
  ListCheck, 
  Play, 
  Layers, 
  RefreshCw 
} from 'lucide-react';

export default function JiraReleaseSection({ 
  pipelineState, 
  onRunPipeline 
}) {
  const [selectedReleaseId, setSelectedReleaseId] = useState('rel-1');
  const [activeReleaseData, setActiveReleaseData] = useState(JIRA_RELEASES_DATA[0]);
  const [isFetched, setIsFetched] = useState(true);
  
  // Track selected FRDs (default all 5 selected)
  const [selectedFrdIds, setSelectedFrdIds] = useState(
    JIRA_RELEASES_DATA[0].frds.map(f => f.id)
  );

  const handleFetchRelease = () => {
    const rel = JIRA_RELEASES_DATA.find(r => r.id === selectedReleaseId);
    if (rel) {
      setActiveReleaseData(rel);
      setSelectedFrdIds(rel.frds.map(f => f.id));
      setIsFetched(true);
    }
  };

  const toggleFrdSelection = (id) => {
    setSelectedFrdIds(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const handleEvaluateClick = () => {
    if (selectedFrdIds.length === 0) {
      alert('Please select at least one FRD to evaluate.');
      return;
    }
    onRunPipeline();
  };

  return (
    <section className="baxter-card jira-compact-section">
      {/* Top Header with Title and Normal-sized Evaluate Button */}
      <div className="jira-compact-topbar">
        <div className="baxter-card-title" style={{ fontSize: '1rem', margin: 0 }}>
          <Layers size={18} className="text-baxter-blue" />
          Jira Requirements &amp; Test Ingestion
        </div>

        <button
          className="btn-run-pipeline"
          disabled={pipelineState === 'running' || selectedFrdIds.length === 0}
          onClick={handleEvaluateClick}
          style={{ padding: '0.55rem 1.25rem', fontSize: '0.875rem' }}
        >
          <Play size={16} fill="currentColor" />
          {pipelineState === 'running' ? 'Evaluating & Parsing...' : 'Evaluate'}
        </button>
      </div>

      {/* 2-Column Grid Layout (Release Box on Left, FRS & Test Cases on Right) */}
      <div className="jira-horizontal-layout">
        
        {/* PART 1 (LEFT): Release Dropdown & Release Button Box */}
        <div className="jira-column release-col">
          <div className="jira-section-box release-box">
            <div className="jira-col-header">
              <Layers size={16} /> Release
            </div>

            <div className="release-controls-inner">
              <select
                id="jira-release-select"
                className="jira-release-dropdown"
                value={selectedReleaseId}
                onChange={(e) => setSelectedReleaseId(e.target.value)}
                disabled={pipelineState === 'running'}
              >
                {JIRA_RELEASES_DATA.map((rel) => (
                  <option key={rel.id} value={rel.id}>
                    {rel.name}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="btn-fetch-release"
                onClick={handleFetchRelease}
                disabled={pipelineState === 'running'}
              >
                <RefreshCw size={14} />
                Release
              </button>
            </div>
          </div>
        </div>

        {/* PART 2 (RIGHT): FRS / FRD Top Box & Manual Test Cases Bottom Box */}
        <div className="jira-column middle-col">
          
          {/* Top Box: FRD */}
          <div className="jira-section-box frs-box">
            <div className="jira-col-header blue-header">
              <FileText size={15} /> FRD
            </div>
            
            <div className="compact-items-grid">
              {activeReleaseData.frds.map((frd, idx) => {
                const isSelected = selectedFrdIds.includes(frd.id);
                return (
                  <label
                    key={frd.id}
                    className={`compact-item-chip ${isSelected ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleFrdSelection(frd.id)}
                    />
                    <span>FRD {idx + 1}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Bottom Box: Manual Test Cases */}
          <div className="jira-section-box mntc-box">
            <div className="jira-col-header blue-header">
              <ListCheck size={15} /> Manual test cases
            </div>
            
            <div className="compact-items-grid">
              {activeReleaseData.manualTestCases.map((tc, idx) => {
                const correspondingFrd = activeReleaseData.frds[idx];
                const isFrdSelected = correspondingFrd && selectedFrdIds.includes(correspondingFrd.id);
                return (
                  <div
                    key={tc.id}
                    className={`compact-item-chip tc-chip ${isFrdSelected ? 'selected' : ''}`}
                  >
                    <span>MNTC {idx + 1}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
