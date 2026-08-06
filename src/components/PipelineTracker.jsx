import React from 'react';
import { Check, Cpu, Loader2 } from 'lucide-react';

export default function PipelineTracker({ stepsState }) {
  const stepsConfig = [
    {
      id: 'parsing',
      title: 'Document Parsing'
    },
    {
      id: 'generation',
      title: 'Generation of Test Cases'
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
      </div>

      {/* Horizontal Connected Node Stepper Pipeline Flow */}
      <div className="stepper-pipeline-container">
        <div className="stepper-track">
          {stepsConfig.map((step, idx) => {
            const stepData = stepsState[step.id];
            const status = stepData.status; // 'pending' | 'running' | 'success'
            
            // Connecting line status to the next node
            let lineClass = 'pending';
            if (status === 'success') {
              lineClass = 'completed';
            } else if (status === 'running') {
              lineClass = 'running';
            }

            return (
              <React.Fragment key={step.id}>
                {/* Stepper Node Item */}
                <div className="stepper-node-item">
                  {/* Circle Icon Badge */}
                  <div className={`node-circle ${status}`}>
                    {status === 'success' && <Check size={24} color="#FFFFFF" strokeWidth={3} />}
                    {status === 'running' && <Loader2 size={22} color="#FFFFFF" className="spin" />}
                    {status === 'pending' && <div className="pending-inner-dot" />}
                  </div>

                  {/* Node Label Details */}
                  <div className="node-details">
                    <div className="node-title">{step.title}</div>
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
