import React, { useState, useEffect, useRef } from 'react';
import BaxterHeader from './components/BaxterHeader';
import InputSection from './components/InputSection';
import PipelineTracker from './components/PipelineTracker';
import TestMetricsCard from './components/TestMetricsCard';
import DownloadZipCard from './components/DownloadZipCard';
import { SAMPLE_FRD, SAMPLE_EXCEL } from './mockData';

export default function App() {
  // Default to empty state ready for file uploads
  const [frdFile, setFrdFile] = useState(null);
  const [excelFile, setExcelFile] = useState(null);

  // Pipeline execution state: 'idle' | 'running' | 'completed'
  const [pipelineState, setPipelineState] = useState('idle');

  // Total Stopwatch Execution Time in seconds
  const [totalExecutionTime, setTotalExecutionTime] = useState(0);

  // Individual Stage execution timer & status states
  const [stepsState, setStepsState] = useState({
    parsing: { status: 'pending', executionTime: 0 },
    generation: { status: 'pending', executionTime: 0 }
  });

  const timerRef = useRef(null);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Main Pipeline Execution Logic
  const handleRunPipeline = () => {
    // Reset states
    setPipelineState('running');
    setTotalExecutionTime(0);
    setStepsState({
      parsing: { status: 'running', executionTime: 0 },
      generation: { status: 'pending', executionTime: 0 }
    });

    const startTime = Date.now();

    // Start global stopwatch timer tick (every 30ms for smooth live timer)
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setTotalExecutionTime((Date.now() - startTime) / 1000);
    }, 30);

    // Stage 1: Document Parsing (1.8s)
    let pTime = 0;
    const pTimer = setInterval(() => {
      pTime += 0.05;
      setStepsState((prev) => ({
        ...prev,
        parsing: { ...prev.parsing, executionTime: pTime }
      }));
    }, 50);

    setTimeout(() => {
      clearInterval(pTimer);
      setStepsState((prev) => ({
        ...prev,
        parsing: { status: 'success', executionTime: 1.85 },
        generation: { status: 'running', executionTime: 0 }
      }));

      // Stage 2: Test Case Generation (2.6s)
      let gTime = 0;
      const gTimer = setInterval(() => {
        gTime += 0.05;
        setStepsState((prev) => ({
          ...prev,
          generation: { ...prev.generation, executionTime: gTime }
        }));
      }, 50);

      setTimeout(() => {
        clearInterval(gTimer);
        clearInterval(timerRef.current);
        setStepsState((prev) => ({
          ...prev,
          generation: { status: 'success', executionTime: 2.60 }
        }));

        // Final pipeline completion
        const finalDuration = (Date.now() - startTime) / 1000;
        setTotalExecutionTime(finalDuration);
        setPipelineState('completed');
      }, 2600);
    }, 1850);
  };

  return (
    <div className="baxter-app">
      {/* Baxter Header */}
      <BaxterHeader pipelineState={pipelineState} />

      {/* Main Container */}
      <main className="baxter-main-content">
        {/* Upload & Setup Section */}
        <InputSection
          frdFile={frdFile}
          setFrdFile={setFrdFile}
          excelFile={excelFile}
          setExcelFile={setExcelFile}
          pipelineState={pipelineState}
          onRunPipeline={handleRunPipeline}
        />

        {/* Side-by-Side Row: Execution Flow & Generated Test Metrics */}
        <div className="flow-metrics-row">
          <PipelineTracker
            pipelineState={pipelineState}
            stepsState={stepsState}
            totalExecutionTime={totalExecutionTime}
          />
          <TestMetricsCard pipelineState={pipelineState} />
        </div>

        {/* Dedicated Separate Box to Download Output in ZIP format */}
        {pipelineState === 'completed' && (
          <DownloadZipCard />
        )}
      </main>
    </div>
  );
}
