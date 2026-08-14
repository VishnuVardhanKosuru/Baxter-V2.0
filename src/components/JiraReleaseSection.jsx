import React, { useState } from 'react';
import {
  FileText,
  ListCheck,
  Play,
  Layers,
  Search,
  Loader2,
  RefreshCw
} from 'lucide-react';

export default function JiraReleaseSection({
  pipelineState,
  onRunPipeline,
  jiraCredentials
}) {
  const [epicKey, setEpicKey] = useState('BANK-101');
  const [epicData, setEpicData] = useState(null);
  const [isFetching, setIsFetching] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  // Track selected FRDs
  const [selectedFrdIds, setSelectedFrdIds] = useState([]);

  const handleFetchEpic = async () => {
    if (!epicKey.trim()) return;
    setIsFetching(true);
    setFetchError(null);
    setEpicData(null);
    setSelectedFrdIds([]);

    try {
      const response = await fetch(`/api/jira/epic/${epicKey.trim()}`, {
        headers: {
          'X-Jira-Url': jiraCredentials?.url || '',
          'X-Jira-Email': jiraCredentials?.email || '',
          'X-Jira-Token': jiraCredentials?.apiToken || '',
          'X-Gemini-Key': jiraCredentials?.geminiApiKey || ''
        }
      });
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || 'Failed to fetch epic details.');
      }

      setEpicData(data.epic);
      setSelectedFrdIds(data.epic.frds.map(f => f.id));
    } catch (err) {
      console.error(err);
      setFetchError(err.message);
    } finally {
      setIsFetching(false);
    }
  };

  const toggleFrdSelection = (id) => {
    setSelectedFrdIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const handleEvaluateClick = () => {
    if (!epicData) {
      alert('Please fetch an epic first.');
      return;
    }
    onRunPipeline(epicKey);
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
          disabled={pipelineState === 'running' || !epicData}
          onClick={handleEvaluateClick}
          style={{ padding: '0.55rem 1.25rem', fontSize: '0.875rem' }}
        >
          <Play size={16} fill="currentColor" />
          {pipelineState === 'running' ? 'Evaluating & Parsing...' : 'Evaluate'}
        </button>
      </div>

      {/* 2-Column Grid Layout (Release Box on Left, FRS & Test Cases on Right) */}
      <div className="jira-horizontal-layout">

        {/* PART 1 (LEFT): Epic Input & Fetch Button Box */}
        <div className="jira-column release-col">
          <div className="jira-section-box release-box">
            <div className="jira-col-header">
              <Search size={16} /> Fetch Epic
            </div>

            <div className="release-controls-inner" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
              <input
                type="text"
                placeholder="Enter Issue Key (e.g., BANK-101)"
                value={epicKey}
                onChange={(e) => setEpicKey(e.target.value)}
                disabled={isFetching || pipelineState === 'running'}
                style={{ padding: '0.5rem', borderRadius: 6, border: '1px solid #CBD5E1', fontSize: '0.875rem' }}
              />

              <button
                type="button"
                className="btn-fetch-release"
                onClick={handleFetchEpic}
                disabled={isFetching || pipelineState === 'running' || !epicKey.trim()}
                style={{ marginTop: '0.5rem' }}
              >
                {isFetching ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
                {isFetching ? 'Fetching...' : 'Fetch Epic'}
              </button>

              {fetchError && (
                <div style={{ color: '#E11D48', fontSize: '0.75rem', marginTop: '0.5rem', wordBreak: 'break-word' }}>
                  {fetchError}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* PART 2 (RIGHT): FRS / FRD Top Box & Manual Test Cases Bottom Box */}
        <div className="jira-column middle-col">

          {/* Top Box: FRD */}
          <div className="jira-section-box frs-box">
            <div className="jira-col-header blue-header">
              <FileText size={15} /> FRDs ({epicData?.frds?.length || 0})
            </div>

            <div className="compact-items-grid" style={{ maxHeight: '130px', overflowY: 'auto' }}>
              {!epicData && !isFetching && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Enter an Epic Key to fetch FRDs.</div>}
              {epicData && epicData.frds.length === 0 && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No FRDs found.</div>}
              {epicData?.frds.map((frd, idx) => {
                const isSelected = selectedFrdIds.includes(frd.id);
                return (
                  <label
                    key={frd.id}
                    className={`compact-item-chip ${isSelected ? 'selected' : ''}`}
                    title={frd.name}
                    style={{ maxWidth: '100%', minWidth: 0 }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleFrdSelection(frd.id)}
                      style={{ flexShrink: 0 }}
                    />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
                      {frd.suggested_name || frd.name}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Bottom Box: Manual Test Cases */}
          <div className="jira-section-box mntc-box">
            <div className="jira-col-header blue-header">
              <ListCheck size={15} /> Manual test cases ({epicData?.manualTestCases?.length || 0})
            </div>

            <div className="compact-items-grid" style={{ maxHeight: '130px', overflowY: 'auto' }}>
              {!epicData && !isFetching && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Enter an Epic Key to fetch test cases.</div>}
              {epicData && epicData.manualTestCases.length === 0 && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No Test Cases found.</div>}
              {epicData?.manualTestCases.map((tc, idx) => {
                // Determine if this test case is "active" based on whether any FRDs are selected.
                // Normally you might map test cases to specific FRDs, but here we just show all test cases for the epic.
                const isActive = selectedFrdIds.length > 0;
                return (
                  <div
                    key={tc.id}
                    className={`compact-item-chip tc-chip ${isActive ? 'selected' : ''}`}
                    title={tc.name}
                    style={{ maxWidth: '100%', minWidth: 0 }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
                      {tc.suggested_name || tc.name}
                    </span>
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
