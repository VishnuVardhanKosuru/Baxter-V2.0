import React, { useState } from 'react';
import { Ticket, CheckCircle, Copy, ExternalLink } from 'lucide-react';

export default function JiraView({ metrics = {} }) {
  const [copied, setCopied] = useState(false);

  const jiraUrl = metrics.jira_project_url || "https://your-domain.atlassian.net/projects/KEY/issues";
  const bugsPushed = metrics.bugs_pushed || 0;
  const syncStatus = metrics.jira_status || (bugsPushed > 0 ? "Synced" : "Waiting...");

  const handleOpenJira = () => {
    window.open(jiraUrl, '_blank', 'noopener,noreferrer');
  };

  const copyUrl = () => {
    navigator.clipboard.writeText(jiraUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Top Header */}
      <div>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A', margin: '0 0 0.25rem 0', letterSpacing: '-0.01em' }}>
          Jira Integration
        </h2>
        <p style={{ fontSize: '0.85rem', color: '#64748B', margin: 0 }}>
          View all the automatically generated test cases directly in your Jira project board.
        </p>
      </div>

      {/* 2 Side-by-Side Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
        
        {/* Card 1: BUGS PUSHED TO JIRA (Light Blue/Purple Tint) */}
        <div style={{
          background: '#F8F7FF',
          border: '1px solid #ECE9FE',
          borderRadius: '0.85rem',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          minHeight: '130px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', fontWeight: 800, color: '#2563EB', letterSpacing: '0.05em' }}>
            <Ticket size={16} color="#2563EB" /> BUGS PUSHED TO JIRA
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#0F172A', marginTop: '0.5rem' }}>
            {bugsPushed}
          </div>
        </div>

        {/* Card 2: SYNC STATUS (Light Mint Green Tint) */}
        <div style={{
          background: '#F0FDF4',
          border: '1px solid #DCFCE7',
          borderRadius: '0.85rem',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          minHeight: '130px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', fontWeight: 800, color: '#16A34A', letterSpacing: '0.05em' }}>
            <CheckCircle size={16} color="#16A34A" /> SYNC STATUS
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0F172A', marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            {syncStatus === 'Synced' ? (
              <span style={{ color: '#16A34A' }}>✅ Synced</span>
            ) : (
              <span style={{ color: '#64748B' }}>⚪ Waiting...</span>
            )}
          </div>
        </div>

      </div>

      {/* Bottom Section: JIRA PROJECT LINK Card */}
      <div style={{
        background: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: '0.85rem',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem'
      }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#475569', letterSpacing: '0.05em' }}>
          JIRA PROJECT LINK
        </div>

        {/* Inner URL Display Container */}
        <div style={{
          background: '#FAFAFA',
          border: '1px solid #E2E8F0',
          borderRadius: '0.75rem',
          padding: '1.1rem 1.5rem',
          textAlign: 'center',
          color: '#475569',
          fontFamily: 'monospace',
          fontSize: '0.85rem',
          wordBreak: 'break-all'
        }}>
          {jiraUrl}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.85rem' }}>
          <button 
            style={{ 
              background: '#FFFFFF', 
              border: '1px solid #CBD5E1', 
              borderRadius: '0.5rem', 
              padding: '0.65rem 1.25rem', 
              fontSize: '0.85rem', 
              fontWeight: 600, 
              color: '#334155',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
            onClick={copyUrl}
          >
            <Copy size={14} /> {copied ? "Copied!" : "Copy Link"}
          </button>

          <button 
            className="btn-primary" 
            onClick={handleOpenJira}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}
          >
            <ExternalLink size={15} /> Open in Jira
          </button>
        </div>
      </div>

    </div>
  );
}
