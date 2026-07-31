import React from 'react';
import { Download } from 'lucide-react';

export default function TesterView({ repo, metrics }) {
  const totalGeneration = metrics.unit_tests + metrics.integration_tests + metrics.bva_tests + metrics.security_tests;

  const handleDownload = () => {
    window.location.href = `http://localhost:8000/api/download-tests?repo=${repo}`;
  };

  return (
    <>
      <div className="grid-cols-4">
        <div className="card metric-card metric-blue">
          <div className="metric-header">UNIT TESTS</div>
          <div className="metric-value">{metrics.unit_tests}</div>
        </div>
        <div className="card metric-card metric-green">
          <div className="metric-header">INTEGRATION TESTS</div>
          <div className="metric-value">{metrics.integration_tests}</div>
        </div>
        <div className="card metric-card metric-orange">
          <div className="metric-header">BVA EDGE CASES</div>
          <div className="metric-value">{metrics.bva_tests}</div>
        </div>
        <div className="card metric-card metric-red">
          <div className="metric-header">SECURITY TESTS</div>
          <div className="metric-value">{metrics.security_tests}</div>
        </div>
      </div>

      <div className="card pane" style={{ minHeight: '200px' }}>
        <div className="pane-header">GENERATED ARTIFACTS</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Download all compiled JUnit `.java` files and Manual `.csv` matrices in a single archive.
        </div>
        <div className="pane-content" style={{ flexDirection: 'column', gap: '1rem', padding: '2rem' }}>
           <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--card-border)', width: '100%', padding: '1rem', borderRadius: 'var(--radius-md)', textAlign: 'center', color: 'var(--text-main)' }}>
             Total Generation: {totalGeneration} files created across all strategies.
           </div>
           <button className="btn-primary" style={{ alignSelf: 'flex-end' }} onClick={handleDownload}>
             <Download size={14} /> Download Test Cases
           </button>
        </div>
      </div>
    </>
  );
}
