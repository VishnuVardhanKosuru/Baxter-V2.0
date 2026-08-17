import React from 'react';
import { Check, Cpu, Loader2, X } from 'lucide-react';

const formatDuration = (seconds) => {
  if (!seconds || seconds <= 0) return null;
  return seconds < 60
    ? `${seconds.toFixed(1)}s`
    : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
};

export default function PipelineTracker({ stepsState, totalExecutionTime }) {
  const totalElapsed = formatDuration(totalExecutionTime);

  const stepsConfig = [
    {
      id: 'parsing',
      title: 'Document Parsing',
      subtitles: {
        pending: 'Not Started',
        running: 'Parsing FRD & Test Cases...',
        success: 'Parsed & Context Extracted',
        failed: 'Parsing Failed'
      }
    },
    {
      id: 'generation',
      title: 'Generation of Automated Test Scripts',
      subtitles: {
        pending: 'Pending Execution',
        running: 'Generating Selenium & Cucumber Scripts...',
        success: 'Selenium & BDD Features Generated',
        failed: 'Generation Failed'
      }
    }
  ];

  return (
    <section className="baxter-card" style={{ padding: '1.05rem 1.35rem' }}>
      <div className="pipeline-header" style={{ borderBottom: 'none', paddingBottom: 0, marginBottom: '0.85rem' }}>
        <div>
          <div className="baxter-card-title" style={{ fontSize: '1.1rem', marginBottom: '0.15rem' }}>
            <Cpu size={20} className="text-baxter-blue" />
            Execution Flow
          </div>
          <div className="baxter-card-subtitle" style={{ marginBottom: 0, fontSize: '0.825rem' }}>
            Real-time stage flow for FRD and manual test case document parsing and test case generation.
          </div>
        </div>

        {totalElapsed && (
          <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 600, letterSpacing: '0.04em' }}>
              TOTAL ELAPSED
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0033A0', fontVariantNumeric: 'tabular-nums' }}>
              {totalElapsed}
            </div>
          </div>
        )}
      </div>

      {/* Horizontal Connected Node Stepper Pipeline Flow */}
      <div className="stepper-pipeline-container">
        <div className="stepper-track">
          {stepsConfig.map((step, idx) => {
            const stepData = stepsState[step.id] || { status: 'pending' };
            const status = stepData.status; // 'pending' | 'running' | 'success' | 'failed'
            const stepElapsed = status === 'success' ? formatDuration(stepData.executionTime) : null;


            // Connecting line status to the next node
            let lineClass = 'pending';
            if (status === 'success') {
              lineClass = 'completed';
            } else if (status === 'running') {
              lineClass = 'running';
            } else if (status === 'failed') {
              lineClass = 'failed';
            }

            return (
              <React.Fragment key={step.id}>
                {/* Stepper Node Item */}
                <div className="stepper-node-item">
                  {/* Circle Icon Badge */}
                  <div className={`node-circle ${status}`} style={status === 'failed' ? { backgroundColor: '#EF4444', borderColor: '#DC2626' } : {}}>
                    {status === 'success' && <Check size={24} color="#FFFFFF" strokeWidth={3} />}
                    {status === 'failed' && <X size={22} color="#FFFFFF" strokeWidth={3} />}
                    {status === 'running' && <Loader2 size={22} color="#FFFFFF" className="spin" />}
                    {status === 'pending' && <div className="pending-inner-dot" />}
                  </div>

                  {/* Node Label Details */}
                  <div className="node-details">
                    <div className="node-title" style={status === 'failed' ? { color: '#DC2626' } : {}}>{step.title}</div>
                    <div className="node-status-sub" style={{ fontSize: '0.75rem', color: status === 'success' ? '#059669' : '#64748B', fontWeight: 600, marginTop: '2px' }}>
                      {step.subtitles[status] || status}
                      {stepElapsed && (
                        <span style={{ color: '#94A3B8', fontWeight: 600 }}> · {stepElapsed}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Connecting Line between nodes */}
                {idx < stepsConfig.length - 1 && (
                  <div className={`stepper-line ${lineClass}`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </section>
  );
}


