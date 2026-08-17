import React, { useState, useEffect } from 'react';
import {
  X,
  DollarSign,
  Cpu,
  Download,
  RefreshCw,
  Zap,
  Activity,
  Layers,
  FileText,
  Clock,
  Key
} from 'lucide-react';

export default function CostMetricsModal({ isOpen, onClose, metrics, onRefresh }) {
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'breakdown' | 'logs'
  const [searchTerm, setSearchTerm] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  if (!isOpen) return null;

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    if (onRefresh) await onRefresh();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const handleDownloadReport = () => {
    window.open('/api/cost/download-report', '_blank');
  };

  const filteredEntries = (metrics?.entries || []).filter(entry => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      entry.phase.toLowerCase().includes(term) ||
      entry.model.toLowerCase().includes(term) ||
      entry.key_alias.toLowerCase().includes(term) ||
      entry.timestamp.toLowerCase().includes(term)
    );
  });

  return (
    <div className="jira-modal-overlay" onClick={onClose}>
      <div
        className="jira-modal-container cost-modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '850px', width: '95%', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* Header */}
        <div className="jira-modal-header" style={{ padding: '1.1rem 1.4rem', borderBottom: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{
              backgroundColor: '#EFF6FF',
              padding: '0.45rem',
              borderRadius: '8px',
              color: '#0033A0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <DollarSign size={20} strokeWidth={2.5} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#002670' }}>
                AI Token & Cost Analytics
              </h3>
              <p style={{ margin: 0, fontSize: '0.785rem', color: '#64748B' }}>
                Real-time tracking of LLM token consumption and costs across agents
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              className="btn-modal-refresh"
              onClick={handleRefreshClick}
              title="Refresh Metrics"
              disabled={isRefreshing}
              style={{
                background: '#F1F5F9',
                border: '1px solid #CBD5E1',
                borderRadius: '6px',
                padding: '0.4rem 0.65rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.785rem',
                fontWeight: 600,
                color: '#334155',
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
              Refresh
            </button>
            <button
              className="jira-modal-close"
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div style={{ padding: '1.25rem 1.4rem', overflowY: 'auto', flex: 1 }}>
          
          {/* Top KPI Summary Cards */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            flexWrap: 'wrap',
            gap: '0.85rem',
            marginBottom: '1.25rem'
          }}>
            {/* Total Cost Card */}
            <div style={{
              background: 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
              border: '1px solid #BFDBFE',
              borderRadius: '10px',
              padding: '0.9rem 1.1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <span style={{ fontSize: '0.785rem', fontWeight: 600, color: '#1E40AF' }}>Total LLM Cost</span>
                <DollarSign size={16} color="#1D4ED8" />
              </div>
              <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#1E3A8A' }}>
                {metrics?.total_cost_formatted || '$0.000000'}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#3B82F6', marginTop: '0.15rem' }}>
                Across {metrics?.total_calls || 0} API Calls
              </div>
            </div>

            {/* Total Tokens Card */}
            <div style={{
              background: 'linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%)',
              border: '1px solid #A7F3D0',
              borderRadius: '10px',
              padding: '0.9rem 1.1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <span style={{ fontSize: '0.785rem', fontWeight: 600, color: '#065F46' }}>Total Tokens</span>
                <Zap size={16} color="#059669" />
              </div>
              <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#064E3B' }}>
                {(metrics?.total_tokens || 0).toLocaleString()}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#10B981', marginTop: '0.15rem' }}>
                In: {(metrics?.total_input_tokens || 0).toLocaleString()} | Out: {(metrics?.total_output_tokens || 0).toLocaleString()}
              </div>
            </div>

            {/* Input vs Output Ratio */}
            <div style={{
              background: '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '10px',
              padding: '0.9rem 1.1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <span style={{ fontSize: '0.785rem', fontWeight: 600, color: '#475569' }}>Avg Cost / Call</span>
                <Activity size={16} color="#64748B" />
              </div>
              <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#0F172A' }}>
                {metrics?.total_calls > 0
                  ? `$${(metrics.total_cost / metrics.total_calls).toFixed(6)}`
                  : '$0.000000'}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#64748B', marginTop: '0.15rem' }}>
                Optimized Multi-Key Router
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div style={{
            display: 'flex',
            borderBottom: '1px solid #E2E8F0',
            marginBottom: '1rem',
            gap: '1.5rem'
          }}>
            <button
              style={{
                background: 'none',
                border: 'none',
                padding: '0.5rem 0',
                fontSize: '0.875rem',
                fontWeight: activeTab === 'summary' ? 700 : 500,
                color: activeTab === 'summary' ? '#0033A0' : '#64748B',
                borderBottom: activeTab === 'summary' ? '2px solid #0033A0' : '2px solid transparent',
                cursor: 'pointer'
              }}
              onClick={() => setActiveTab('summary')}
            >
              Agent Breakdown
            </button>
            <button
              style={{
                background: 'none',
                border: 'none',
                padding: '0.5rem 0',
                fontSize: '0.875rem',
                fontWeight: activeTab === 'logs' ? 700 : 500,
                color: activeTab === 'logs' ? '#0033A0' : '#64748B',
                borderBottom: activeTab === 'logs' ? '2px solid #0033A0' : '2px solid transparent',
                cursor: 'pointer'
              }}
              onClick={() => setActiveTab('logs')}
            >
              Recent Execution Logs ({metrics?.entries?.length || 0})
            </button>
          </div>

          {/* Tab 1: Agent & Phase Breakdown */}
          {activeTab === 'summary' && (
            <div>
              {(!metrics?.phases || metrics.phases.length === 0) ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#64748B', fontSize: '0.875rem' }}>
                  No LLM agent calls recorded yet. Run a parsing or test generation pipeline to start tracking tokens and cost.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  {metrics.phases.map((p, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: '8px',
                        padding: '0.95rem 1.15rem',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Layers size={16} color="#0033A0" />
                          <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#002670' }}>
                            {p.phase} Agent
                          </span>
                          <span className="badge-tag badge-pending" style={{ fontSize: '0.725rem' }}>
                            {p.calls} calls
                          </span>
                        </div>
                        <span style={{ fontWeight: 800, fontSize: '1rem', color: '#0033A0' }}>
                          {p.cost_formatted}
                        </span>
                      </div>

                      <div style={{
                        display: 'flex',
                        justifyContent: 'center',
                        flexWrap: 'wrap',
                        gap: '1.5rem',
                        fontSize: '0.785rem',
                        color: '#475569',
                        backgroundColor: '#F8FAFC',
                        padding: '0.65rem 0.85rem',
                        borderRadius: '6px'
                      }}>
                        <div>
                          <span style={{ color: '#64748B' }}>Input Tokens: </span>
                          <strong>{p.input_tokens.toLocaleString()}</strong>
                        </div>
                        <div>
                          <span style={{ color: '#64748B' }}>Output Tokens: </span>
                          <strong>{p.output_tokens.toLocaleString()}</strong>
                        </div>
                        <div>
                          <span style={{ color: '#64748B' }}>Total Tokens: </span>
                          <strong>{p.total_tokens.toLocaleString()}</strong>
                        </div>
                        <div>
                          <span style={{ color: '#64748B' }}>Models: </span>
                          <span title={p.models.join(', ')} style={{ fontWeight: 600 }}>
                            {p.models.join(', ') || 'Default'}
                          </span>
                        </div>
                      </div>

                      {/* Sub-breakdown per API Key */}
                      {p.key_breakdown && p.key_breakdown.length > 0 && (
                        <div style={{ marginTop: '0.85rem', borderTop: '1px solid #E2E8F0', paddingTop: '0.85rem' }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748B', marginBottom: '0.5rem', textAlign: 'center', letterSpacing: '0.05em' }}>
                            BREAKDOWN BY API KEY
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'center' }}>
                            {p.key_breakdown.map((kb, kbIdx) => (
                              <div key={kbIdx} style={{
                                display: 'flex',
                                justifyContent: 'center',
                                flexWrap: 'wrap',
                                gap: '1.5rem',
                                backgroundColor: '#F1F5F9',
                                padding: '0.5rem 1rem',
                                borderRadius: '6px',
                                fontSize: '0.75rem',
                                color: '#475569',
                                width: '100%'
                              }}>
                                <div style={{ fontWeight: 600, color: '#0033A0', minWidth: '90px' }}>{kb.key_alias}</div>
                                <div>Calls: <strong>{kb.calls}</strong></div>
                                <div>In: <strong>{kb.input_tokens.toLocaleString()}</strong></div>
                                <div>Out: <strong>{kb.output_tokens.toLocaleString()}</strong></div>
                                <div style={{ color: '#047857', fontWeight: 700 }}>{kb.cost_formatted}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Recent Execution Logs */}
          {activeTab === 'logs' && (
            <div>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.85rem' }}>
                <input
                  type="text"
                  placeholder="Filter logs by phase, model, or key..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    flex: 1,
                    padding: '0.45rem 0.75rem',
                    border: '1px solid #CBD5E1',
                    borderRadius: '6px',
                    fontSize: '0.825rem'
                  }}
                />
              </div>

              <div style={{
                maxHeight: '280px',
                overflowY: 'auto',
                border: '1px solid #E2E8F0',
                borderRadius: '6px',
                backgroundColor: '#F8FAFC'
              }}>
                {filteredEntries.length === 0 ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: '#64748B', fontSize: '0.825rem' }}>
                    No matching logs found.
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.785rem' }}>
                    <thead>
                      <tr style={{ background: '#F1F5F9', borderBottom: '1px solid #CBD5E1', textAlign: 'left', color: '#475569' }}>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Timestamp</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Phase</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Model / Key</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Tokens (In / Out)</th>
                        <th style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredEntries.slice().reverse().map((entry, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #E2E8F0' }}>
                          <td style={{ padding: '0.45rem 0.75rem', color: '#64748B', whiteSpace: 'nowrap' }}>
                            {entry.timestamp}
                          </td>
                          <td style={{ padding: '0.45rem 0.75rem' }}>
                            <span className="badge-tag badge-pending" style={{ fontSize: '0.7rem' }}>
                              {entry.phase}
                            </span>
                          </td>
                          <td style={{ padding: '0.45rem 0.75rem', color: '#334155', fontWeight: 500 }}>
                            {entry.model} <span style={{ color: '#64748B', fontSize: '0.725rem' }}>({entry.key_alias})</span>
                          </td>
                          <td style={{ padding: '0.45rem 0.75rem', color: '#475569' }}>
                            {entry.input_tokens.toLocaleString()} / {entry.output_tokens.toLocaleString()}
                          </td>
                          <td style={{ padding: '0.45rem 0.75rem', textAlign: 'right', fontWeight: 700, color: '#0033A0' }}>
                            ${entry.cost.toFixed(6)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

        </div>

        {/* Footer with Actions */}
        <div style={{
          padding: '0.85rem 1.4rem',
          borderTop: '1px solid #E2E8F0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#F8FAFC'
        }}>
          <span style={{ fontSize: '0.785rem', color: '#64748B' }}>
            Data source: <code>output/cost_tracking.txt</code>
          </span>

          <div style={{ display: 'flex', gap: '0.65rem' }}>
            <button
              type="button"
              className="btn-download-cost-report"
              onClick={handleDownloadReport}
              style={{
                backgroundColor: '#0033A0',
                color: '#FFFFFF',
                border: 'none',
                padding: '0.55rem 1.1rem',
                borderRadius: '6px',
                fontSize: '0.825rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                cursor: 'pointer',
                boxShadow: '0 2px 4px rgba(0,51,160,0.15)'
              }}
            >
              <Download size={15} />
              Download Audit Report (.txt)
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
