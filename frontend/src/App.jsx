import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import PipelineTracker from './components/PipelineTracker';
import ScannerView from './components/ScannerView';
import TesterView from './components/TesterView';
import JiraView from './components/JiraView';

function App() {
  const [repo, setRepo] = useState('supriya-daita/LibraryManagementSystem');
  const [currentStep, setCurrentStep] = useState(0);
  const [activeTab, setActiveTab] = useState('scanner');
  const [isRunning, setIsRunning] = useState(false);
  
  const [metrics, setMetrics] = useState({
    files_scanned: 0,
    functions_found: 0,
    graph_nodes: 0,
    graph_edges: 0,
    security_vulns: 0,
    unit_tests: 0,
    integration_tests: 0,
    bva_tests: 0,
    security_tests: 0,
    jira_tests_created: 0,
    jira_project_url: ''
  });

  useEffect(() => {
    const eventSource = new EventSource('http://localhost:8000/api/stream');

    eventSource.addEventListener('state_update', (event) => {
      const state = JSON.parse(event.data);
      setCurrentStep(state.currentStep);
      setIsRunning(state.isRunning);
      setMetrics(state.metrics);
    });

    eventSource.addEventListener('log_update', (event) => {
      // Logs are just printed on python console, but we could hook them here if desired.
    });

    return () => {
      eventSource.close();
    };
  }, []);

  const runPipeline = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo })
      });
      const data = await response.json();
      if (data.status === 'ok') {
        setIsRunning(true);
      } else {
        alert(data.message);
      }
    } catch (e) {
      alert("Failed to connect to backend api at http://localhost:8000");
    }
  };

  return (
    <div className="app-container">
      <Header repo={repo} setRepo={setRepo} onRun={runPipeline} isRunning={isRunning} />
      <PipelineTracker currentStep={currentStep} />
      
      <div>
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'scanner' ? 'active' : ''}`}
            onClick={() => setActiveTab('scanner')}
          >
            Scanner View
          </button>
          <button 
            className={`tab ${activeTab === 'tester' ? 'active' : ''}`}
            onClick={() => setActiveTab('tester')}
          >
            Tester View
          </button>
          <button 
            className={`tab ${activeTab === 'jira' ? 'active' : ''}`}
            onClick={() => setActiveTab('jira')}
          >
            Jira Integration
          </button>
        </div>

        {activeTab === 'scanner' && <ScannerView repo={repo} metrics={metrics} />}
        {activeTab === 'tester' && <TesterView repo={repo} metrics={metrics} />}
        {activeTab === 'jira' && <JiraView metrics={metrics} />}
      </div>
    </div>
  );
}

export default App;
