import React, { useState, useEffect, useRef, useCallback } from 'react';
import BaxterHeader from './components/BaxterHeader';
import InputSection from './components/InputSection';
import PipelineTracker from './components/PipelineTracker';
import TestMetricsCard from './components/TestMetricsCard';
import DownloadZipCard from './components/DownloadZipCard';
import JiraCredentialsModal from './components/JiraCredentialsModal';
import CostMetricsModal from './components/CostMetricsModal';

export default function App() {
  const [frdFile, setFrdFile] = useState(null);
  const [excelFile, setExcelFile] = useState(null);

  const [pipelineState, setPipelineState] = useState('idle');
  const [parsedResult, setParsedResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const [totalExecutionTime, setTotalExecutionTime] = useState(0);
  const [stepsState, setStepsState] = useState({
    parsing: { status: 'pending', executionTime: 0 },
    generation: { status: 'pending', executionTime: 0 },
  });

  const [isJiraModalOpen, setIsJiraModalOpen] = useState(true);
  const [isCostModalOpen, setIsCostModalOpen] = useState(false);
  const [costMetrics, setCostMetrics] = useState(null);

  const [jiraCredentials, setJiraCredentials] = useState(null);
  const [jiraConnected, setJiraConnected] = useState(false);
  const [activeMode, setActiveMode] = useState('manual');

  const timerRef = useRef(null);

  const fetchCostMetrics = useCallback(async () => {
    try {
      const res = await fetch('/api/cost/metrics');
      const data = await res.json();
      if (data?.success) {
        setCostMetrics(data.metrics);
      }
    } catch (e) {
      console.warn('Could not fetch cost metrics:', e);
    }
  }, []);

  useEffect(() => {
    fetchCostMetrics();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchCostMetrics]);

  const handleSaveJiraCredentials = (creds) => {
    setJiraCredentials(creds);
    if (creds.mode === 'jira') {
      setJiraConnected(true);
      setActiveMode('jira');
    } else {
      setJiraConnected(false);
      setActiveMode('manual');
    }
  };

  const handleRunPipeline = async (epicKey = null) => {
    setPipelineState('running');
    setErrorMessage('');
    setParsedResult(null);
    setTotalExecutionTime(0);
    setStepsState({
      parsing: { status: 'running', executionTime: 0 },
      generation: { status: 'pending', executionTime: 0 },
    });

    const startTime = Date.now();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(
      () => setTotalExecutionTime((Date.now() - startTime) / 1000),
      50,
    );

    if (activeMode === 'jira' && epicKey) {
      try {
        const res = await fetch('/api/jira/evaluate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Jira-Url': jiraCredentials?.url || '',
            'X-Jira-Email': jiraCredentials?.email || '',
            'X-Jira-Token': jiraCredentials?.apiToken || '',
            'X-Gemini-Key': jiraCredentials?.geminiApiKey || ''
          },
          body: JSON.stringify({ issue_key: epicKey })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.message || 'Failed to download Jira files');
        }

        const totalDuration = (Date.now() - startTime) / 1000;
        setStepsState({
          parsing: { status: 'success', executionTime: totalDuration },
          generation: { status: 'pending', executionTime: 0 },
        });
        setTotalExecutionTime(totalDuration);
        setParsedResult({ type: 'jira_download', files: data.files });
        setPipelineState('completed');
      } catch (err) {
        console.error('Jira download error:', err);
        setErrorMessage(err.message || 'Failed to connect to backend');
        setStepsState(prev => ({
          ...prev,
          parsing: { status: 'failed', executionTime: 0 },
        }));
        setPipelineState('idle');
      } finally {
        if (timerRef.current) clearInterval(timerRef.current);
      }
      return;
    }

    const formData = new FormData();
    if (frdFile?.rawFile && excelFile?.rawFile) {
      formData.append('frd_file', frdFile.rawFile);
      formData.append('tc_file', excelFile.rawFile);
    } else {
      formData.append('use_sample', 'true');
    }

    try {
      // ── Stage 1: Document Parsing ───────────────────────────────────────
      const s1Res = await fetch('/api/stage1-parse', {
        method: 'POST',
        body: formData,
      });
      const s1Data = await s1Res.json();
      if (!s1Res.ok || !s1Data.success) {
        throw new Error(s1Data.detail || s1Data.message || 'Stage 1 parsing failed');
      }

      const s1Result = s1Data.result;
      const s1Time = (Date.now() - startTime) / 1000;

      setStepsState({
        parsing: { status: 'success', executionTime: s1Time },
        generation: { status: 'running', executionTime: 0 },
      });

      // ── Stage 2: Test Code Generation ──────────────────────────────────
      const s2Res = await fetch('/api/stage2-generate', {
        method: 'POST',
      });
      const s2Data = await s2Res.json();
      if (!s2Res.ok || !s2Data.success) {
        throw new Error(s2Data.detail || s2Data.message || 'Stage 2 generation failed');
      }

      const s2Result = s2Data.result;
      const totalDuration = (Date.now() - startTime) / 1000;
      const s2Time = totalDuration - s1Time;

      setStepsState({
        parsing: { status: 'success', executionTime: s1Time },
        generation: { status: 'success', executionTime: s2Time },
      });

      setTotalExecutionTime(totalDuration);
      setParsedResult(s2Result);
      setPipelineState('completed');
      fetchCostMetrics();

    } catch (err) {
      console.error('Pipeline error:', err);
      setErrorMessage(err.message || 'Failed to connect to backend');
      setStepsState(prev => ({
        parsing: prev.parsing.status === 'success'
          ? prev.parsing
          : { status: 'failed', executionTime: 0 },
        generation: { status: 'failed', executionTime: 0 },
      }));
      setPipelineState('idle');
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
      fetchCostMetrics();
    }
  };

  return (
    <div className="baxter-app">
      <BaxterHeader
        onOpenJiraModal={() => setIsJiraModalOpen(true)}
        hasJiraCredentials={jiraConnected}
        onOpenCostModal={() => setIsCostModalOpen(true)}
        costMetrics={costMetrics}
      />

      <JiraCredentialsModal
        isOpen={isJiraModalOpen}
        onClose={() => setIsJiraModalOpen(false)}
        onSave={handleSaveJiraCredentials}
        initialCredentials={jiraCredentials}
      />

      <CostMetricsModal
        isOpen={isCostModalOpen}
        onClose={() => setIsCostModalOpen(false)}
        metrics={costMetrics}
        onRefresh={fetchCostMetrics}
      />

      <main className="baxter-main-content">
        {errorMessage && (
          <div style={{
            padding: '0.85rem 1.15rem',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            color: '#991B1B',
            borderRadius: 8,
            marginBottom: '1rem',
            fontSize: '0.875rem',
          }}>
            <strong>Error:</strong> {errorMessage}
          </div>
        )}

        <InputSection
          frdFile={frdFile}
          setFrdFile={setFrdFile}
          excelFile={excelFile}
          setExcelFile={setExcelFile}
          pipelineState={pipelineState}
          onRunPipeline={handleRunPipeline}
          jiraConnected={jiraConnected}
          jiraCredentials={jiraCredentials}
          activeMode={activeMode}
          setActiveMode={setActiveMode}
        />

        <div className="flow-metrics-row">
          <PipelineTracker
            pipelineState={pipelineState}
            stepsState={stepsState}
            totalExecutionTime={totalExecutionTime}
          />
          <TestMetricsCard
            pipelineState={pipelineState}
            parsedResult={parsedResult}
          />
        </div>

        {pipelineState === 'completed' && <DownloadZipCard />}
      </main>
    </div>
  );
}


