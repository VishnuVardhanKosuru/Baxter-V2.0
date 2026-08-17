import React, { useState } from 'react';
import { KeyRound, Mail, Link, Check, ShieldCheck, Sparkles, UploadCloud, ArrowLeft } from 'lucide-react';

export default function JiraCredentialsModal({ isOpen, onClose, onSave, initialCredentials }) {
  const [modalMode, setModalMode] = useState('jira'); // 'jira' or 'manual'
  
  const initialKeys = initialCredentials?.geminiApiKey ? initialCredentials.geminiApiKey.split(',') : [''];
  const [numKeys, setNumKeys] = useState(initialKeys.length || 1);
  const [geminiApiKeys, setGeminiApiKeys] = useState(initialKeys);
  
  const [jiraUrl, setJiraUrl] = useState(initialCredentials?.url || '');
  const [email, setEmail] = useState(initialCredentials?.email || '');
  const [apiToken, setApiToken] = useState(initialCredentials?.apiToken || '');
  
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [validationError, setValidationError] = useState('');

  if (!isOpen) return null;

  const handleNumKeysChange = (e) => {
    const val = parseInt(e.target.value) || 1;
    const count = Math.max(1, Math.min(val, 10)); // Limit 1 to 10 keys
    setNumKeys(count);
    setGeminiApiKeys(prev => {
      const newKeys = [...prev];
      while (newKeys.length < count) newKeys.push('');
      return newKeys.slice(0, count);
    });
  };

  const handleKeyChange = (index, val) => {
    setGeminiApiKeys(prev => {
      const newKeys = [...prev];
      newKeys[index] = val;
      return newKeys;
    });
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    const validKeys = geminiApiKeys.map(k => k.trim()).filter(Boolean);
    if (validKeys.length === 0) {
      setValidationError('Please enter at least one Gemini API Key to connect.');
      return;
    }
    setValidationError('');
    if (onSave) {
      onSave({
        geminiApiKey: validKeys.join(','),
        url: jiraUrl,
        email,
        apiToken,
        mode: 'manual'
      });
    }
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 1000);
  };

  const handleJiraSubmit = (e) => {
    e.preventDefault();
    if (!jiraUrl.trim() || !email.trim() || !apiToken.trim()) {
      setValidationError('Please fill in all Jira credentials (URL, Email, API Token).');
      return;
    }
    const validKeys = geminiApiKeys.map(k => k.trim()).filter(Boolean);
    if (validKeys.length === 0) {
      setValidationError('Please enter at least one Gemini API Key.');
      return;
    }
    setValidationError('');
    if (onSave) {
      onSave({
        geminiApiKey: validKeys.join(','),
        url: jiraUrl,
        email,
        apiToken,
        mode: 'jira'
      });
    }
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 1000);
  };

  const switchToManualMode = () => {
    setValidationError('');
    setModalMode('manual');
  };

  const switchToJiraMode = () => {
    setValidationError('');
    setModalMode('jira');
  };

  return (
    <div className="jira-modal-overlay">
      <div className="jira-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="jira-modal-header">
          <div className="jira-modal-title">
            <div className="jira-icon-badge">
              {modalMode === 'jira' ? (
                <ShieldCheck size={20} className="text-baxter-blue" />
              ) : (
                <UploadCloud size={20} className="text-baxter-blue" />
              )}
            </div>
            <div>
              <h3>{modalMode === 'jira' ? 'Jira Integration Credentials' : 'Manual Connection'}</h3>
              <p className="jira-modal-subtitle">
                {modalMode === 'jira'
                  ? 'Connect your Jira instance to import requirements & test cases'
                  : 'Enter your Gemini API key for manual file uploads'}
              </p>
            </div>
          </div>
        </div>

        {/* Modal Body depending on mode */}
        {modalMode === 'jira' ? (
          /* JIRA FORM MODE */
          <form onSubmit={handleJiraSubmit} className="jira-modal-form">
            {/* 1. Jira Instance URL */}
            <div className="jira-form-group">
              <label htmlFor="jira-url">
                <Link size={15} /> Jira Instance URL
              </label>
              <input
                id="jira-url"
                type="url"
                placeholder="https://your-domain.atlassian.net"
                value={jiraUrl}
                onChange={(e) => setJiraUrl(e.target.value)}
                required
              />
            </div>

            {/* 2. Jira Email */}
            <div className="jira-form-group">
              <label htmlFor="jira-email">
                <Mail size={15} /> Jira Email Address
              </label>
              <input
                id="jira-email"
                type="email"
                placeholder="your-jira-email@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            {/* 3. Jira API Token */}
            <div className="jira-form-group">
              <label htmlFor="jira-token">
                <KeyRound size={15} /> Jira API Token
              </label>
              <input
                id="jira-token"
                type="password"
                placeholder="Enter your Jira API token"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                required
              />
            </div>

            {/* 4. Number of API Keys */}
            <div className="jira-form-group">
              <label htmlFor="num-api-keys">
                Number of Gemini API Keys
              </label>
              <input
                id="num-api-keys"
                type="number"
                min="1"
                max="10"
                value={numKeys}
                onChange={handleNumKeysChange}
              />
            </div>

            {/* 5. Dynamic Gemini API Keys */}
            {Array.from({ length: numKeys }).map((_, idx) => (
              <div className="jira-form-group" key={idx}>
                <label>
                  <Sparkles size={15} /> Gemini API Key {idx + 1}
                </label>
                <input
                  type="password"
                  placeholder="Enter your Gemini API Key (e.g. AIzaSy...)"
                  value={geminiApiKeys[idx] || ''}
                  onChange={(e) => handleKeyChange(idx, e.target.value)}
                  required
                />
              </div>
            ))}

            {validationError && (
              <div className="jira-error-message" style={{ color: '#DC2626', fontSize: '0.8rem', fontWeight: 600 }}>
                {validationError}
              </div>
            )}

            {savedSuccess && (
              <div className="jira-success-message">
                <Check size={16} /> Connected successfully!
              </div>
            )}

            {/* Action Buttons: Connect Manually & Connect to Jira */}
            <div className="jira-modal-actions">
              <button
                type="button"
                className="jira-btn-cancel"
                onClick={switchToManualMode}
              >
                Connect Manually
              </button>

              <button
                type="submit"
                className="jira-btn-submit"
              >
                Connect to Jira
              </button>
            </div>
          </form>
        ) : (
          /* MANUAL FORM MODE (Only Gemini API Key) */
          <form onSubmit={handleManualSubmit} className="jira-modal-form">
            <div style={{ marginBottom: '0.2rem' }}>
              <button
                type="button"
                className="sample-btn"
                onClick={switchToJiraMode}
                style={{ fontSize: '0.775rem', padding: '0.25rem 0.6rem', border: 'none', background: 'none', color: '#0033A0' }}
              >
                <ArrowLeft size={13} style={{ display: 'inline', marginRight: 3 }} />
                Back to Jira Connection
              </button>
            </div>

            {/* Number of API Keys */}
            <div className="jira-form-group">
              <label htmlFor="num-api-keys-manual">
                Number of Gemini API Keys
              </label>
              <input
                id="num-api-keys-manual"
                type="number"
                min="1"
                max="10"
                value={numKeys}
                onChange={handleNumKeysChange}
              />
            </div>

            {/* Dynamic Gemini API Keys */}
            {Array.from({ length: numKeys }).map((_, idx) => (
              <div className="jira-form-group" key={idx}>
                <label>
                  <Sparkles size={15} /> Gemini API Key {idx + 1}
                </label>
                <input
                  type="password"
                  placeholder="Enter your Gemini API Key (e.g. AIzaSy...)"
                  value={geminiApiKeys[idx] || ''}
                  onChange={(e) => handleKeyChange(idx, e.target.value)}
                  required
                  autoFocus={idx === 0}
                />
              </div>
            ))}

            {validationError && (
              <div className="jira-error-message" style={{ color: '#DC2626', fontSize: '0.8rem', fontWeight: 600 }}>
                {validationError}
              </div>
            )}

            {savedSuccess && (
              <div className="jira-success-message">
                <Check size={16} /> Connected successfully!
              </div>
            )}

            {/* Single Action Button: Connect */}
            <div className="jira-modal-actions" style={{ justifyContent: 'flex-end' }}>
              <button
                type="submit"
                className="jira-btn-submit"
              >
                {savedSuccess ? 'Connected' : 'Connect'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
