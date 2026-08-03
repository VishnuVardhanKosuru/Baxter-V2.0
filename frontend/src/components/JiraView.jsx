import React from 'react';
import { ExternalLink, CheckCircle, Copy, TicketCheck } from 'lucide-react';

export default function JiraView({ metrics }) {
  const handleOpenJira = () => {
    if (metrics.jira_project_url) {
      window.open(metrics.jira_project_url, '_blank', 'noopener,noreferrer');
    } else {
      alert('Jira project URL is not available yet. Please ensure the pipeline has pushed tests to Jira.');
    }
  };

  const copyUrl = () => {
    if (metrics.jira_project_url) {
      navigator.clipboard.writeText(metrics.jira_project_url);
    }
  };

  return (
    <>
      <div className="grid-cols-2">
        <div className="card metric-card metric-blue">
          <div className="metric-header"><TicketCheck size={14} /> BUGS PUSHED TO JIRA</div>
          <div className="metric-value">{metrics.jira_tests_created || 0}</div>
        </div>
        <div className="card metric-card metric-green">
          <div className="metric-header"><CheckCircle size={14} /> SYNC STATUS</div>
          <div className="metric-value" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
            {metrics.jira_tests_created > 0 ? '● Active' : '○ Waiting...'}
          </div>
        </div>
      </div>

      <div className="card pane" style={{ minHeight: '200px' }}>
        <div className="pane-header">JIRA PROJECT LINK</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          View all the automatically generated test cases directly in your Jira project board.
        </div>
        <div className="pane-content" style={{ flexDirection: 'column', gap: '1rem', padding: '2rem' }}>
           <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--card-border)', width: '100%', padding: '1rem', borderRadius: 'var(--radius-md)', textAlign: 'center', color: 'var(--text-muted)', wordBreak: 'break-all', fontFamily: 'monospace', fontSize: '0.85rem' }}>
             {metrics.jira_project_url || "https://your-domain.atlassian.net/projects/KEY/issues"}
           </div>
           
           <div style={{ display: 'flex', gap: '0.75rem', alignSelf: 'flex-end' }}>
             <button className="btn-icon" style={{ border: '1px solid var(--card-border)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }} onClick={copyUrl}>
               <Copy size={14} /> Copy Link
             </button>
             <button className="btn-primary" onClick={handleOpenJira}>
               <ExternalLink size={14} /> Open in Jira
             </button>
           </div>
        </div>
      </div>
    </>
  );
}
