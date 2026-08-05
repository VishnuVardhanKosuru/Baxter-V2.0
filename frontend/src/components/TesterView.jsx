import React from 'react';
import { 
  Box, Smile, CircleDashed, AlertTriangle, Package, ShieldCheck, Download, Zap
} from 'lucide-react';

export default function TesterView({ repo, metrics = {} }) {
  const handleDownload = () => {
    window.location.href = `http://localhost:8000/api/download-tests?repo=${encodeURIComponent(repo || '')}`;
  };

  const hasScannedData = metrics && (metrics.files_scanned > 0 || metrics.graph_nodes > 0 || metrics.test_cases_generated > 0 || metrics.unit_tests > 0);

  // Strictly dynamic counts: 0 when un-scanned or before running pipeline
  const unitTotal = hasScannedData ? (metrics.unit_tests || 0) : 0;
  const unitHappy = hasScannedData ? (metrics.unit_happy || 0) : 0;
  const unitBoundary = hasScannedData ? (metrics.bva_tests || 0) : 0;
  const unitNegative = hasScannedData ? (metrics.unit_negative || 0) : 0;
  const unitMock = hasScannedData ? (metrics.unit_mock || 0) : 0;
  const unitSecurity = hasScannedData ? (metrics.security_tests || 0) : 0;

  const integrationTotal = hasScannedData ? (metrics.integration_tests || 0) : 0;
  const integrationHappy = hasScannedData ? (metrics.integration_happy || 0) : 0;
  const integrationBoundary = hasScannedData ? (metrics.integration_bva || 0) : 0;
  const integrationNegative = hasScannedData ? (metrics.integration_negative || 0) : 0;
  const integrationMock = hasScannedData ? (metrics.integration_mock || 0) : 0;
  const integrationSecurity = hasScannedData ? (metrics.integration_security || 0) : 0;

  const totalFiles = hasScannedData ? (metrics.total_files || (unitTotal + integrationTotal > 0 ? 6 : 0)) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Top Header */}
      <div>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A', margin: '0 0 0.25rem 0', letterSpacing: '-0.01em' }}>
          Test Generation Summary
        </h2>
        <p style={{ fontSize: '0.85rem', color: '#64748B', margin: 0 }}>
          Overview of generated test cases by type and strategy.
        </p>
      </div>

      {/* 2 Large Side-by-Side Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
        
        {/* Card 1: Unit Tests (Purple Theme) */}
        <div style={{
          background: '#F8F7FF',
          border: '1px solid #ECE9FE',
          borderRadius: '0.85rem',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          {/* Header Row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: '2rem',
                height: '2rem',
                borderRadius: '0.5rem',
                background: '#EDE9FE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#7C3AED'
              }}>
                <Box size={16} />
              </div>
              <span style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>Unit Tests</span>
            </div>

            <div style={{
              background: '#EDE9FE',
              color: '#6D28D9',
              border: '1px solid #DDD6FE',
              borderRadius: '1rem',
              padding: '0.2rem 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              Total: {unitTotal.toLocaleString()}
            </div>
          </div>

          {/* 5 Strategy Sub-Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.6rem' }}>
            {/* Happy Path */}
            <div style={{ background: '#F0FDF4', border: '1px solid #DCFCE7', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#DCFCE7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Smile size={14} color="#16A34A" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Happy Path</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{unitHappy}</span>
            </div>

            {/* Boundary */}
            <div style={{ background: '#FFF7ED', border: '1px solid #FFEDD5', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#FFEDD5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CircleDashed size={14} color="#EA580C" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Boundary</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{unitBoundary}</span>
            </div>

            {/* Negative */}
            <div style={{ background: '#FFF1F2', border: '1px solid #FFE4E6', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertTriangle size={14} color="#DC2626" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Negative</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{unitNegative}</span>
            </div>

            {/* Mock */}
            <div style={{ background: '#F0F9FF', border: '1px solid #E0F2FE', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#E0F2FE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Package size={14} color="#0284C7" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Mock</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{unitMock}</span>
            </div>

            {/* Security */}
            <div style={{ background: '#F5F3FF', border: '1px solid #EDE9FE', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#F3E8FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ShieldCheck size={14} color="#9333EA" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Security</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{unitSecurity}</span>
            </div>
          </div>
        </div>

        {/* Card 2: Integration Tests (Green Theme) */}
        <div style={{
          background: '#F0FDF4',
          border: '1px solid #DCFCE7',
          borderRadius: '0.85rem',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          {/* Header Row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: '2rem',
                height: '2rem',
                borderRadius: '0.5rem',
                background: '#DCFCE7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#16A34A'
              }}>
                <Box size={16} />
              </div>
              <span style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>Integration Tests</span>
            </div>

            <div style={{
              background: '#DCFCE7',
              color: '#15803D',
              border: '1px solid #BBF7D0',
              borderRadius: '1rem',
              padding: '0.2rem 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              Total: {integrationTotal.toLocaleString()}
            </div>
          </div>

          {/* 5 Strategy Sub-Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.6rem' }}>
            {/* Happy Path */}
            <div style={{ background: '#FFFFFF', border: '1px solid #DCFCE7', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#DCFCE7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Smile size={14} color="#16A34A" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Happy Path</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{integrationHappy}</span>
            </div>

            {/* Boundary */}
            <div style={{ background: '#FFF7ED', border: '1px solid #FFEDD5', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#FFEDD5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CircleDashed size={14} color="#EA580C" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Boundary</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{integrationBoundary}</span>
            </div>

            {/* Negative */}
            <div style={{ background: '#FFF1F2', border: '1px solid #FFE4E6', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertTriangle size={14} color="#DC2626" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Negative</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{integrationNegative}</span>
            </div>

            {/* Mock */}
            <div style={{ background: '#F0F9FF', border: '1px solid #E0F2FE', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#E0F2FE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Package size={14} color="#0284C7" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Mock</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{integrationMock}</span>
            </div>

            {/* Security */}
            <div style={{ background: '#F5F3FF', border: '1px solid #EDE9FE', borderRadius: '0.75rem', padding: '0.85rem 0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.4rem' }}>
              <div style={{ width: '1.8rem', height: '1.8rem', borderRadius: '50%', background: '#F3E8FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ShieldCheck size={14} color="#9333EA" />
              </div>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#0F172A' }}>Security</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginTop: '0.1rem' }}>{integrationSecurity}</span>
            </div>
          </div>
        </div>

      </div>

      {/* Bottom Section: Generated Artifacts Card */}
      <div style={{
        background: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: '0.85rem',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            width: '2rem',
            height: '2rem',
            borderRadius: '50%',
            background: '#FFF1F2',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FF4D6D'
          }}>
            <Download size={16} />
          </div>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              Generated Tests
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#64748B', margin: '0.1rem 0 0 0' }}>
              Download all compiled JUnit <code style={{ background: '#F1F5F9', padding: '0.1rem 0.35rem', borderRadius: '0.25rem', fontSize: '0.75rem' }}>.java</code> files and Manual <code style={{ background: '#F1F5F9', padding: '0.1rem 0.35rem', borderRadius: '0.25rem', fontSize: '0.75rem' }}>.csv</code> matrices in a single archive.
            </p>
          </div>
        </div>

        {/* Inner White Container Bar */}
        <div style={{
          background: '#FFFFFF',
          border: '1px solid #E2E8F0',
          borderRadius: '0.75rem',
          padding: '1.25rem 1.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#0F172A' }}>
            Total Generation: {totalFiles} files created across all strategies.
          </span>

          <button 
            className="btn-primary" 
            onClick={handleDownload}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.25rem', fontSize: '0.85rem' }}
          >
            <Download size={14} /> Download Test Cases
          </button>
        </div>
      </div>

    </div>
  );
}
