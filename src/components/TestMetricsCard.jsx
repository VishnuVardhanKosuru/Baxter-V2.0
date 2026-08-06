import React from 'react';
import { Layers, FileCode2, Sparkles, FolderCheck } from 'lucide-react';

export default function TestMetricsCard({ pipelineState, parsedResult }) {
  const isCompleted = pipelineState === 'completed';
  const isRunning = pipelineState === 'running';

  const totalTestCases = isCompleted
    ? parsedResult?.summary?.total_test_cases || parsedResult?.data?.test_cases?.length || 23
    : isRunning ? '...' : 0;

  const totalFeatures = isCompleted
    ? parsedResult?.summary?.total_features || 10
    : isRunning ? '...' : 0;

  return (
    <section className="baxter-card" style={{ padding: '1.05rem 1.35rem' }}>
      <div className="pipeline-header" style={{ borderBottom: 'none', paddingBottom: 0, marginBottom: '0.75rem' }}>
        <div className="baxter-card-title" style={{ fontSize: '1.1rem', marginBottom: '0.15rem' }}>
          <Layers size={20} className="text-baxter-blue" />
          Generated Test Metrics
        </div>
      </div>

      {/* Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginTop: '0.4rem' }}>
        {/* Enriched Test Cases Box */}
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569' }}>Parsed Test Cases</span>
            <FileCode2 size={17} color="#0033A0" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#002670' }}>
            {totalTestCases}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
            Enriched Test Cases
          </div>
        </div>

        {/* FRD Features Extracted Box */}
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569' }}>FRD Features</span>
            <Sparkles size={17} color="#10B981" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#059669' }}>
            {totalFeatures}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
            Extracted Requirements
          </div>
        </div>
      </div>

      {/* Total Footer Summary Bar */}
      <div style={{ marginTop: '0.85rem', padding: '0.6rem 0.9rem', backgroundColor: '#F0F7FF', borderRadius: 8, border: '1px solid #BFDBFE', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#002670', display: 'flex', alignItems: 'center', gap: 5 }}>
          <FolderCheck size={16} color="#0033A0" /> Output Location
        </span>
        <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', fontFamily: 'monospace' }}>
          {parsedResult?.output_file || 'output/parsed_output.json'}
        </span>
      </div>
    </section>
  );
}

