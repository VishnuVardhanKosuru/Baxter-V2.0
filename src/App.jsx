import React, { useState, useEffect, useRef } from 'react';
import BaxterHeader from './components/BaxterHeader';
import InputSection from './components/InputSection';
import PipelineTracker from './components/PipelineTracker';
import TestMetricsCard from './components/TestMetricsCard';
import DownloadZipCard from './components/DownloadZipCard';
import JiraCredentialsModal from './components/JiraCredentialsModal';

import { GENERATED_TEST_CASES } from './mockData';

import AgentTokenCostCard from './components/AgentTokenCostCard';

export default function App() {
  const [frdFile,   setFrdFile]   = useState(null);
  const [excelFile, setExcelFile] = useState(null);

  const [pipelineState, setPipelineState] = useState('idle');
  const [parsedResult,  setParsedResult]  = useState(null);
  const [errorMessage,  setErrorMessage]  = useState('');

  const [totalExecutionTime, setTotalExecutionTime] = useState(0);
  const [stepsState, setStepsState] = useState({
    parsing:    { status: 'pending', executionTime: 0 },
    generation: { status: 'pending', executionTime: 0 },
  });

  const [isJiraModalOpen, setIsJiraModalOpen] = useState(true);
  const [jiraCredentials, setJiraCredentials] = useState(null);
  const [jiraConnected, setJiraConnected] = useState(false);
  const [activeMode, setActiveMode] = useState('manual');

  const timerRef = useRef(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

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

  const handleRunPipeline = async () => {
    setPipelineState('running');
    setErrorMessage('');
    setParsedResult(null);
    setTotalExecutionTime(0);
    setStepsState({
      parsing:    { status: 'running', executionTime: 0 },
      generation: { status: 'pending', executionTime: 0 },
    });

    const startTime = Date.now();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(
      () => setTotalExecutionTime((Date.now() - startTime) / 1000),
      50,
    );

    const formData = new FormData();
    if (frdFile?.rawFile && excelFile?.rawFile) {
      formData.append('frd_file', frdFile.rawFile);
      formData.append('tc_file',  excelFile.rawFile);
    } else {
      formData.append('use_sample', 'true');
    }

    try {
      // ── Stage 1: Document Parsing ───────────────────────────────────────
      let s1Result;
      try {
        const s1Res = await fetch('/api/stage1-parse', {
          method: 'POST',
          body: formData,
        });
        const s1Data = await s1Res.json();
        if (!s1Res.ok || !s1Data.success) {
          throw new Error(s1Data.detail || s1Data.message || 'Stage 1 parsing failed');
        }
        s1Result = s1Data.result;
      } catch (backendErr) {
        console.warn('Backend server unavailable. Falling back to Mock Data mode:', backendErr.message);
        // Simulate Stage 1 parsing delay for mock mode
        await new Promise((resolve) => setTimeout(resolve, 1500));
        s1Result = {
          status: 'success',
          frd_file: frdFile?.name || 'FRD_Baxter_Sigma_Spectrum_Infusion_Pump_v3.4.docx',
          tc_file: excelFile?.name || 'Manual_Test_Cases_Infusion_Module_v1.2.docx',
        };
      }

      const s1Time = (Date.now() - startTime) / 1000;

      setStepsState({
        parsing:    { status: 'success', executionTime: s1Time },
        generation: { status: 'running', executionTime: 0 },
      });

      // ── Stage 2: Test Code Generation ──────────────────────────────────
      let s2Result;
      try {
        const s2Res = await fetch('/api/stage2-generate', {
          method: 'POST',
        });
        const s2Data = await s2Res.json();
        if (!s2Res.ok || !s2Data.success) {
          throw new Error(s2Data.detail || s2Data.message || 'Stage 2 generation failed');
        }
        s2Result = s2Data.result;
      } catch (backendErr) {
        console.warn('Backend server unavailable. Falling back to Mock Data mode:', backendErr.message);
        // Simulate Stage 2 generation delay for mock mode
        await new Promise((resolve) => setTimeout(resolve, 1800));
        s2Result = {
          summary: {
            selenium_count: 5,
            cucumber_count: 5,
            total_generated: 10,
          },
          tests_dir: 'output/tests/ (Mock)',
          test_cases: GENERATED_TEST_CASES,
        };
      }

      const totalDuration = (Date.now() - startTime) / 1000;
      const s2Time = totalDuration - s1Time;

      setStepsState({
        parsing:    { status: 'success', executionTime: s1Time },
        generation: { status: 'success', executionTime: s2Time },
      });
      
      setTotalExecutionTime(totalDuration);
      setParsedResult(s2Result);
      setPipelineState('completed');

    } catch (err) {
      console.error('Pipeline error:', err);
      setErrorMessage(err.message || 'Failed to complete pipeline');
      setStepsState(prev => ({
        parsing:    prev.parsing.status === 'success'
          ? prev.parsing
          : { status: 'failed', executionTime: 0 },
        generation: { status: 'failed', executionTime: 0 },
      }));
      setPipelineState('idle');
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  return (
    <div className="baxter-app">
      <BaxterHeader
        onOpenJiraModal={() => setIsJiraModalOpen(true)}
        hasJiraCredentials={jiraConnected}
      />

      <JiraCredentialsModal
        isOpen={isJiraModalOpen}
        onClose={() => setIsJiraModalOpen(false)}
        onSave={handleSaveJiraCredentials}
        initialCredentials={jiraCredentials}
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

        <AgentTokenCostCard
          pipelineState={pipelineState}
          parsedResult={parsedResult}
          jiraConnected={jiraConnected}
        />

        {pipelineState === 'completed' && <DownloadZipCard />}
      </main>
    </div>
  );
}


