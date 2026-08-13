import React from 'react';
import { ShieldCheck, CheckCircle } from 'lucide-react';

export default function BaxterHeader({ onOpenJiraModal, hasJiraCredentials }) {
  return (
    <header className="baxter-navbar">
      <div className="baxter-navbar-container">
        <div className="baxter-brand-group">
          {/* Baxter Signature Logo styling */}
          <span className="baxter-logo-text">Baxter</span>
          <div className="baxter-divider"></div>
          <div>
            <div className="baxter-app-title">
              Test Automation Intelligence Platform
            </div>
          </div>
        </div>

        <div>
          <button
            className={`jira-header-btn ${hasJiraCredentials ? 'connected' : ''}`}
            onClick={onOpenJiraModal}
            title="Configure Jira Integration Credentials"
          >
            {hasJiraCredentials ? <CheckCircle size={16} /> : <ShieldCheck size={16} />}
            {hasJiraCredentials ? 'Jira Connected' : 'Jira Credentials'}
          </button>
        </div>
      </div>
    </header>
  );
}

