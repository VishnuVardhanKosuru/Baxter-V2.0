import React from 'react';
import { Layers, FileCode2, Sparkles, FolderCheck } from 'lucide-react';

export default function TestMetricsCard({ pipelineState, parsedResult }) {
  const isCompleted = pipelineState === 'completed';
  const isRunning = pipelineState === 'running';

  if (parsedResult?.type === 'jira_download') {
    return (
      <section className="baxter-card" style={{ padding: '1.05rem 1.35rem' }}>
        <div className="pipeline-header" style={{ borderBottom: 'none', paddingBottom: 0, marginBottom: '0.75rem' }}>
          <div className="baxter-card-title" style={{ fontSize: '1.1rem', margin: 0 }}>
            <Layers size={20} className="text-baxter-blue" />
            Jira Files Downloaded
          </div>
        </div>
        <div style={{ maxHeight: '180px', overflowY: 'auto', marginBottom: '0.85rem' }}>
          {!parsedResult.files || parsedResult.files.length === 0 ? (
             <div style={{ fontSize: '0.825rem', color: '#64748B' }}>No FRDs or Test Cases found to download.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {parsedResult.files.map((file, i) => (
                <div key={i} style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6, padding: '0.5rem 0.75rem', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', minWidth: 0, gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden', minWidth: 0, flex: 1 }}>
                    <FolderCheck size={14} color="#0033A0" style={{ flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }} title={file.saved_name}>
                      {file.saved_name}
                    </span>
                  </div>
                  <span className={`badge-tag ${file.category === 'FRD' ? 'badge-high' : 'badge-success'}`} style={{ flexShrink: 0 }}>
                    {file.category}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ padding: '0.6rem 0.9rem', backgroundColor: '#F0F7FF', borderRadius: 8, border: '1px solid #BFDBFE', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#002670', display: 'flex', alignItems: 'center', gap: 5 }}>
            <FolderCheck size={16} color="#0033A0" /> Saved Location
          </span>
          <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', fontFamily: 'monospace' }}>
            input_modules/
          </span>
        </div>
      </section>
    );
  }

  const seleniumCount = isCompleted
    ? (parsedResult?.summary?.selenium_count ?? parsedResult?.data?.test_cases?.length ?? 0)
    : isRunning ? '...' : 0;

  const cucumberCount = isCompleted
    ? (parsedResult?.summary?.cucumber_count ?? parsedResult?.data?.test_cases?.length ?? 0)
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
        {/* Selenium Scripts Box */}
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569' }}>Selenium Tests</span>
            <FileCode2 size={17} color="#0033A0" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#002670' }}>
            {seleniumCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
            WebDriver Scripts (.py)
          </div>
        </div>

        {/* Cucumber BDD Features Box */}
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569' }}>Cucumber Tests</span>
            <Sparkles size={17} color="#10B981" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#059669' }}>
            {cucumberCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
            Gherkin BDD Features (.feature)
          </div>
        </div>
      </div>

      {/* Total Footer Summary Bar */}
      <div style={{ marginTop: '0.85rem', padding: '0.6rem 0.9rem', backgroundColor: '#F0F7FF', borderRadius: 8, border: '1px solid #BFDBFE', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#002670', display: 'flex', alignItems: 'center', gap: 5 }}>
          <FolderCheck size={16} color="#0033A0" /> Test Artifacts Location
        </span>
        <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', fontFamily: 'monospace' }}>
          {parsedResult?.tests_dir || 'output/tests/'}
        </span>
      </div>
    </section>
  );
}


