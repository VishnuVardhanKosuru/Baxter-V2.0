import React from 'react';

export default function BaxterHeader() {
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

        {/* Clean Header - Brand Group Only */}
      </div>
    </header>
  );
}
