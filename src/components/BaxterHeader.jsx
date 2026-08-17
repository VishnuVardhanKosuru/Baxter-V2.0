import React from 'react';
import { ShieldCheck, CheckCircle, DollarSign } from 'lucide-react';

export default function BaxterHeader({
  onOpenJiraModal,
  hasJiraCredentials,
  onOpenCostModal,
  costMetrics
}) {
  const formattedCost = costMetrics?.total_cost != null
    ? `$${costMetrics.total_cost.toFixed(4)}`
    : '$0.0000';

  const totalTokens = costMetrics?.total_tokens || 0;
  const tokenDisplay = totalTokens > 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens;

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

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {/* Dynamic AI Cost & Token Button */}
          <button
            className="cost-header-btn"
            onClick={onOpenCostModal}
            title="View Real-Time AI Token & Cost Breakdown"
          >
            <DollarSign size={15} strokeWidth={2.5} color="#0033A0" />
            <span style={{ fontWeight: 700, color: '#002670' }}>{formattedCost}</span>
            {totalTokens > 0 && (
              <span className="cost-token-badge">
                {tokenDisplay} tok
              </span>
            )}
          </button>

          {/* Jira Connected Button */}
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


