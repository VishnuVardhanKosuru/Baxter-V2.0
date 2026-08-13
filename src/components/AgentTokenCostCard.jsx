import React from 'react';
import { Bot, Cpu, Sparkles, DollarSign, Layers } from 'lucide-react';
import { MOCK_AGENT_TELEMETRY } from '../mockData';

export default function AgentTokenCostCard({ parsedResult }) {
  // Use backend telemetry or fallback to mock data agents
  const agents = parsedResult?.agent_telemetry?.agents || MOCK_AGENT_TELEMETRY.agents;
  const rates = parsedResult?.agent_telemetry?.pricingRates || MOCK_AGENT_TELEMETRY.pricingRates;

  const calculateCost = (inputTokens, outputTokens) => {
    const inputCost = (inputTokens / 1000000) * rates.inputPer1M;
    const outputCost = (outputTokens / 1000000) * rates.outputPer1M;
    return inputCost + outputCost;
  };

  // Calculate totals for all agents combined
  const totalInputTokens = agents.reduce((acc, a) => acc + (a.inputTokens || 0), 0);
  const totalOutputTokens = agents.reduce((acc, a) => acc + (a.outputTokens || 0), 0);
  const totalCombinedCost = agents.reduce((acc, a) => acc + calculateCost(a.inputTokens || 0, a.outputTokens || 0), 0);

  return (
    /* Big Box Container */
    <section className="baxter-card" style={{ padding: '1.25rem 1.4rem', marginTop: '1.25rem' }}>
      {/* Big Box Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1.2rem', paddingBottom: '0.75rem', borderBottom: '1px solid #E2E8F0' }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, backgroundColor: '#E0F2FE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Bot size={20} color="#0033A0" />
        </div>
        <div>
          <div className="baxter-card-title" style={{ fontSize: '1.15rem', color: '#002670' }}>
            AI Agent Token Usage & Cost
          </div>
          <p style={{ fontSize: '0.8rem', color: '#64748B', margin: 0 }}>
            Token consumption and execution cost per AI agent & combined totals
          </p>
        </div>
      </div>

      {/* Grid of 3 Small Boxes for the 3 Agents */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.1rem' }}>
        {agents.map((agent) => {
          const cost = calculateCost(agent.inputTokens, agent.outputTokens);

          return (
            /* Small Box for each Agent */
            <div
              key={agent.id}
              style={{
                backgroundColor: '#F8FAFC',
                border: '1px solid #CBD5E1',
                borderRadius: 10,
                padding: '1.1rem 1.15rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.85rem',
                boxShadow: '0 2px 6px rgba(0, 0, 0, 0.03)',
              }}
            >
              {/* Small Box Title */}
              <div style={{ fontSize: '1rem', fontWeight: 700, color: '#002670', borderBottom: '1px solid #E2E8F0', paddingBottom: '0.5rem' }}>
                {agent.name}
              </div>

              {/* 1. Input Tokens Used */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#FFFFFF', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #E2E8F0' }}>
                <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569', display: 'flex', alignItems: 'center', gap: 5 }}>
                  <Cpu size={15} color="#2563EB" /> Input Tokens Used
                </span>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1E293B' }}>
                  {agent.inputTokens.toLocaleString()}
                </span>
              </div>

              {/* 2. Output Tokens Used */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#FFFFFF', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #E2E8F0' }}>
                <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#475569', display: 'flex', alignItems: 'center', gap: 5 }}>
                  <Sparkles size={15} color="#10B981" /> Output Tokens Used
                </span>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1E293B' }}>
                  {agent.outputTokens.toLocaleString()}
                </span>
              </div>

              {/* 3. Total Cost */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#EFF6FF', padding: '0.65rem 0.8rem', borderRadius: 6, border: '1px solid #BFDBFE' }}>
                <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', display: 'flex', alignItems: 'center', gap: 5 }}>
                  <DollarSign size={15} color="#0033A0" /> Total Cost
                </span>
                <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#002670', fontFamily: 'monospace' }}>
                  ${cost.toFixed(5)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Overall Totals Bar for the whole 3 Agents combined */}
      <div style={{ marginTop: '1.35rem' }}>
        <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#002670', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Layers size={17} color="#0033A0" /> Total Pipeline Telemetry
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.85rem' }}>
          {/* Total Input Tokens Used */}
          <div style={{ backgroundColor: '#F0F7FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Cpu size={16} color="#0033A0" /> Total Input Tokens
            </span>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#002670' }}>
              {totalInputTokens.toLocaleString()}
            </span>
          </div>

          {/* Total Output Tokens Used */}
          <div style={{ backgroundColor: '#F0F7FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Sparkles size={16} color="#0033A0" /> Total Output Tokens
            </span>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#002670' }}>
              {totalOutputTokens.toLocaleString()}
            </span>
          </div>

          {/* Total Cost for whole 3 Agents */}
          <div style={{ backgroundColor: '#F0F7FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.825rem', fontWeight: 700, color: '#0033A0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <DollarSign size={16} color="#0033A0" /> Total Combined Cost
            </span>
            <span style={{ fontSize: '1.2rem', fontWeight: 800, color: '#002670', fontFamily: 'monospace' }}>
              ${totalCombinedCost.toFixed(5)}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
