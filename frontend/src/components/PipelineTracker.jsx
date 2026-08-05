import React from 'react';
import { Check, Clock, GitBranch, Search, Share2, Target, Cpu, TicketCheck } from 'lucide-react';

const STEPS = [
  { label: "Repository Fetch", icon: GitBranch },
  { label: "Code Scan", icon: Search },
  { label: "Knowledge Graph", icon: Share2 },
  { label: "Strategy Injection", icon: Target },
  { label: "Test Generation", icon: Cpu },
  { label: "Jira Integration", icon: TicketCheck },
];

export default function PipelineTracker({ currentStep = 0, elapsedTime = "0s" }) {
  // currentStep: 0 = idle, 1..6 = step index active, 7 = complete
  const totalSteps = STEPS.length;
  const activeCount = Math.max(0, currentStep - 1);
  const progressPercent = currentStep === 0 ? 0 : Math.min((activeCount / (totalSteps - 1)) * 100, 100);

  return (
    <div className="tracker-card" style={{ padding: '1.25rem 1.5rem', background: '#FFFFFF', borderRadius: '1rem', border: '1px solid #E2E8F0' }}>
      
      {/* Left Title Box */}
      <div className="tracker-left" style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div style={{
          width: '2.5rem', 
          height: '2.5rem', 
          borderRadius: '0.75rem', 
          background: '#FFF1F2', 
          border: '1px solid #FECDD3',
          color: '#FF4D6D', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center'
        }}>
          <GitBranch size={20} />
        </div>
        <div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.01em' }}>Pipeline Progress</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Real-time execution status</div>
        </div>
      </div>

      {/* Stepper Grid Container */}
      <div style={{ flex: 1, position: 'relative', margin: '0 2.5rem', display: 'flex', alignItems: 'center' }}>
        
        {/* Continuous Connecting Line */}
        <div style={{
          position: 'absolute',
          top: '1.3rem',
          left: '2rem',
          right: '2rem',
          height: '3px',
          background: '#E2E8F0',
          zIndex: 0,
          borderRadius: '2px'
        }}>
          <div style={{
            height: '100%',
            width: `${progressPercent}%`,
            background: '#10B981',
            borderRadius: '2px',
            transition: 'width 0.4s ease'
          }}></div>
        </div>

        {/* 6 Stepper Nodes */}
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', position: 'relative', zIndex: 1 }}>
          {STEPS.map((step, index) => {
            const stepNum = index + 1;
            const isCompleted = currentStep > stepNum || currentStep === 7;
            const isRunning = currentStep === stepNum;

            let statusText = "Pending";
            if (isCompleted) statusText = "Completed";
            else if (isRunning) statusText = "Running";

            const IconComponent = step.icon;

            return (
              <div key={step.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', flex: 1, minWidth: '90px' }}>
                <div style={{
                  width: '2.6rem',
                  height: '2.6rem',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isCompleted ? '#10B981' : isRunning ? '#FF4D6D' : '#F1F5F9',
                  border: isCompleted ? '2px solid #10B981' : isRunning ? '2px solid #FF4D6D' : '2px solid #CBD5E1',
                  color: isCompleted || isRunning ? '#FFFFFF' : '#64748B',
                  boxShadow: isRunning ? '0 0 0 4px rgba(255, 77, 109, 0.2)' : 'none',
                  transition: 'all 0.3s ease'
                }}>
                  {isCompleted ? <Check size={18} strokeWidth={3} /> : <IconComponent size={16} />}
                </div>

                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0F172A', textAlign: 'center', whiteSpace: 'nowrap' }}>
                  {step.label}
                </div>

                <div style={{ fontSize: '0.7rem', color: isRunning ? '#FF4D6D' : isCompleted ? '#10B981' : '#94A3B8', fontWeight: 500 }}>
                  {statusText}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Execution Time Card */}
      <div style={{
        background: '#FFF1F2',
        border: '1px solid #FECDD3',
        padding: '0.75rem 1.5rem',
        borderRadius: '0.85rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: '150px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#FF4D6D', fontWeight: 700 }}>
          <Clock size={14} /> Execution Time
        </div>
        <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', marginTop: '0.1rem' }}>
          {elapsedTime}
        </div>
      </div>

    </div>
  );
}
