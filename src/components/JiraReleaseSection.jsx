import React, { useState } from 'react';
import {
  FileText,
  ListCheck,
  Play,
  Layers,
  Search,
  Loader2,
  RefreshCw,
  ChevronDown
} from 'lucide-react';

/**
 * Reads a response body as JSON, surfacing a clear message when the backend
 * returns HTML (e.g. a proxy error page while the server is restarting) instead
 * of the JSON the caller expects.
 */
async function parseJsonResponse(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (parseError) {
    console.error('Non-JSON response from backend:', parseError, text.slice(0, 200));
    throw new Error(
      `Server returned an invalid response (status ${response.status}). The backend may be restarting.`,
    );
  }
}

export default function JiraReleaseSection({
  pipelineState,
  onRunPipeline,
  jiraCredentials
}) {
  const [epicKey, setEpicKey] = useState('');
  const [epicData, setEpicData] = useState(null);
  const [isFetching, setIsFetching] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  
  // Track available epics from Jira
  const [availableEpics, setAvailableEpics] = useState([]);
  const [isFetchingEpics, setIsFetchingEpics] = useState(false);

  // Custom Dropdown state
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Track selected FRDs
  const [selectedFrdIds, setSelectedFrdIds] = useState([]);

  const handleLoadEpics = React.useCallback(async () => {
    setIsFetchingEpics(true);
    setFetchError(null);
    try {
      const response = await fetch('/api/jira/epics', {
        headers: {
          'X-Jira-Url': jiraCredentials?.url || '',
          'X-Jira-Email': jiraCredentials?.email || '',
          'X-Jira-Token': jiraCredentials?.apiToken || ''
        }
      });

      const data = await parseJsonResponse(response);
      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || 'Failed to fetch epics.');
      }

      const epics = data.epics || [];
      setAvailableEpics(epics);
      setEpicKey((current) => {
        if (current || epics.length === 0) return current;
        setSearchQuery(epics[0].key);
        return epics[0].key;
      });
    } catch (err) {
      console.error(err);
      setFetchError(err.message);
    } finally {
      setIsFetchingEpics(false);
    }
  }, [jiraCredentials]);

  React.useEffect(() => {
    if (jiraCredentials?.url && jiraCredentials?.apiToken) {
      handleLoadEpics();
    }
  }, [jiraCredentials, handleLoadEpics]);

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
      
      const data = await parseJsonResponse(response);
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
    onRunPipeline(epicKey, selectedFrdIds);
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
          disabled={pipelineState === 'running' || !epicData || selectedFrdIds.length === 0}
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
            <div className="jira-col-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div><Search size={16} /> Fetch Epic</div>
              <button 
                onClick={handleLoadEpics} 
                disabled={isFetchingEpics}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#0033A0', display: 'flex', alignItems: 'center', fontSize: '0.75rem' }}
              >
                <RefreshCw size={12} className={isFetchingEpics ? 'spin' : ''} style={{ marginRight: '4px' }} />
                Reload Epics
              </button>
            </div>

            <div className="release-controls-inner" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
              <div style={{ position: 'relative' }}>
                <div
                  style={{ display: 'flex', border: '1px solid #CBD5E1', borderRadius: 6, padding: '0.5rem', background: '#fff', cursor: 'text' }}
                  onClick={() => setIsDropdownOpen(true)}
                >
                  <input
                    type="text"
                    placeholder={availableEpics.length > 0 ? "Search or Select Epic..." : "No Epics Loaded"}
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setIsDropdownOpen(true);
                      setEpicKey(e.target.value);
                    }}
                    onFocus={() => setIsDropdownOpen(true)}
                    onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
                    style={{ border: 'none', outline: 'none', width: '100%', fontSize: '0.875rem' }}
                    disabled={isFetching || pipelineState === 'running'}
                  />
                  <ChevronDown size={16} style={{ color: '#64748b', alignSelf: 'center', cursor: 'pointer' }} onClick={() => setIsDropdownOpen(!isDropdownOpen)} />
                </div>

                {isDropdownOpen && (
                  <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: '#fff', border: '1px solid #CBD5E1', borderRadius: 6, marginTop: 4, zIndex: 10, maxHeight: 200, overflowY: 'auto', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
                    {availableEpics
                      .filter(epic => {
                        // Show all epics when the search matches an already-selected key
                        // (i.e., user hasn't typed a custom filter). Only filter when
                        // the user is actively narrowing the list.
                        const q = searchQuery.trim().toLowerCase();
                        if (!q) return true;
                        const isSelectedKey = availableEpics.some(e => e.key.toLowerCase() === q);
                        if (isSelectedKey) return true;
                        return epic.key.toLowerCase().includes(q) || (epic.summary || '').toLowerCase().includes(q);
                      })
                      .map(epic => (
                      <div
                        key={epic.key}
                        style={{ padding: '0.5rem', cursor: 'pointer', fontSize: '0.875rem', borderBottom: '1px solid #f1f5f9' }}
                        onClick={() => {
                          setEpicKey(epic.key);
                          setSearchQuery(epic.key);
                          setIsDropdownOpen(false);
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        <strong>{epic.key}</strong>
                      </div>
                    ))}
                    {availableEpics.length === 0 && (
                      <div style={{ padding: '0.5rem', fontSize: '0.875rem', color: '#64748b', textAlign: 'center' }}>
                        Click "Reload Epics" to fetch.
                      </div>
                    )}
                  </div>
                )}
              </div>

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
              <FileText size={15} /> Selected FRDs ({selectedFrdIds.length}/{epicData?.frds?.length || 0})
            </div>

            <div className="compact-items-grid" style={{ maxHeight: '130px', overflowY: 'auto' }}>
              {!epicData && !isFetching && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Enter an Epic Key to fetch FRDs.</div>}
              {epicData && epicData.frds.length === 0 && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No FRDs found.</div>}
              {epicData?.frds.map((frd) => {
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
              <ListCheck size={15} /> Selected Test Cases ({
                epicData?.manualTestCases?.filter((_, idx) => {
                  const relatedFrd = epicData?.frds[idx];
                  return relatedFrd ? selectedFrdIds.includes(relatedFrd.id) : false;
                }).length || 0
              }/{epicData?.manualTestCases?.length || 0})
            </div>

            <div className="compact-items-grid" style={{ maxHeight: '130px', overflowY: 'auto' }}>
              {!epicData && !isFetching && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Enter an Epic Key to fetch test cases.</div>}
              {epicData && epicData.manualTestCases.length === 0 && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No Test Cases found.</div>}
              {epicData?.manualTestCases.map((tc, idx) => {
                // Determine if this test case is "active" based on whether its paired FRD is selected
                const relatedFrd = epicData?.frds[idx];
                const isActive = relatedFrd ? selectedFrdIds.includes(relatedFrd.id) : false;
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
