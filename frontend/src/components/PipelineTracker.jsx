import React from 'react';
import { Check, GitBranch, Share2, GitCompare, Target, Cpu, TicketCheck } from 'lucide-react';

const STEPS = [
  { label: "Sync Repository", icon: GitBranch },
  { label: "Build Knowledge Graph", icon: Share2 },
  { label: "Delta Calculation", icon: GitCompare },
  { label: "Strategy Injection", icon: Target },
  { label: "Generating Tests", icon: Cpu },
  { label: "Jira Integration", icon: TicketCheck },
];

export default function PipelineTracker({ currentStep }) {
  // currentStep: 0 = idle, 1-6 = active on that step, 7+ = all complete
  const totalSteps = STEPS.length;
  const completedCount = Math.max(0, currentStep - 1);
  const progress = currentStep === 0 ? 0 : Math.min((completedCount / (totalSteps - 1)) * 100, 100);
  
  return (
    <div className="card tracker-container">
      <div className="tracker-title">
        <div className="live-dot"></div>
        <span className="tracker-title-text">LIVE PIPELINE TRACKER</span>
      </div>
      <div className="steps">
        <div className="steps-line">
          <div className="steps-progress" style={{ width: `${progress}%` }}></div>
        </div>
        {STEPS.map((step, index) => {
          const stepNum = index + 1;
          let statusClass = "";
          if (currentStep > stepNum) statusClass = "completed";
          else if (currentStep === stepNum) statusClass = "active";
          
          const IconComponent = step.icon;
          
          return (
            <div key={step.label} className={`step ${statusClass}`}>
              <div className="step-circle">
                {statusClass === "completed" ? (
                  <Check size={16} strokeWidth={3} />
                ) : (
                  <IconComponent size={14} />
                )}
              </div>
              <div className="step-label">{step.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
