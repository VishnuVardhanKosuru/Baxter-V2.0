import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import PipelineTracker from './components/PipelineTracker';
import ScannerView from './components/ScannerView';
import TesterView from './components/TesterView';
import JiraView from './components/JiraView';
import { Search, TestTube, Share2 } from 'lucide-react';

function App() {
  const [repo, setRepo] = useState('');
  const [currentStep, setCurrentStep] = useState(0); // 0 = Fresh/Idle state on refresh
  const [activeTab, setActiveTab] = useState('scanner');
  const [isRunning, setIsRunning] = useState(false);
  const [elapsedTime, setElapsedTime] = useState('0s');
  
  const [metrics, setMetrics] = useState({
    files_scanned: 0,
    lines_analyzed: 0,
    functions_found: 0,
    classes: 0,
    modules_packages: 0,
    test_cases_generated: 0,
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
      if (state.currentStep !== undefined) setCurrentStep(state.currentStep);
      if (state.isRunning !== undefined) setIsRunning(state.isRunning);
      if (state.elapsed_time !== undefined) setElapsedTime(state.elapsed_time);
      if (state.repo_name) setRepo(state.repo_name);
      if (state.metrics) setMetrics(prev => ({ ...prev, ...state.metrics }));
    });

    return () => {
      eventSource.close();
    };
  }, []);

  const sanitizeRepoInput = (raw) => {
    if (!raw) return '';
    let clean = raw.trim();
    clean = clean.replace(/^https?:\/\/github\.com\//i, '');
    clean = clean.replace(/\.git$/i, '');
    clean = clean.replace(/\/$/, '');
    return clean;
  };

  const runPipeline = async () => {
    const cleanRepo = sanitizeRepoInput(repo);
    try {
      const response = await fetch('http://localhost:8000/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo: cleanRepo })
      });
      const data = await response.json();
      if (data.status === 'ok') {
        setIsRunning(true);
      } else {
        alert(data.message);
      }
    } catch (e) {
      alert("Failed to connect to backend API at http://localhost:8000");
    }
  };

  return (
    <div className="app-container">
      <Header 
        repo={repo} 
        setRepo={setRepo} 
        onRun={runPipeline}
        isRunning={isRunning} 
      />

      <PipelineTracker currentStep={currentStep} elapsedTime={elapsedTime} />
      
      <div>
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'scanner' ? 'active' : ''}`}
            onClick={() => setActiveTab('scanner')}
          >
            <Search size={16} /> Scanner Agent
          </button>
          <button 
            className={`tab ${activeTab === 'tester' ? 'active' : ''}`}
            onClick={() => setActiveTab('tester')}
          >
            <TestTube size={16} /> Test Generator Agent
          </button>
          <button 
            className={`tab ${activeTab === 'jira' ? 'active' : ''}`}
            onClick={() => setActiveTab('jira')}
          >
            <Share2 size={16} /> Jira Integration
          </button>
        </div>

        {activeTab === 'scanner' && <ScannerView repo={repo} metrics={metrics} currentStep={currentStep} />}
        {activeTab === 'tester' && <TesterView repo={repo} metrics={metrics} />}
        {activeTab === 'jira' && <JiraView metrics={metrics} />}
      </div>
    </div>
  );
}

export default App;
