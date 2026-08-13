import React, { useState } from 'react';
import { Archive, Download, Loader2 } from 'lucide-react';
import JSZip from 'jszip';
import { MOCK_AUTOMATED_SCRIPT_CONTENT } from '../mockData';

export default function DownloadZipCard() {
  const [isZipping, setIsZipping] = useState(false);

  const handleDownloadZip = async () => {
    setIsZipping(true);
    try {
      // 1. Try downloading zip from backend /api/download-zip
      const res = await fetch('/api/download-zip');
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `baxter_generated_tests_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
      }

      // 2. Fallback client-side zip generation
      const zip = new JSZip();
      zip.file('Baxter_Automated_Suite.spec.ts', MOCK_AUTOMATED_SCRIPT_CONTENT);

      const content = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(content);
      const a = document.createElement('a');
      a.href = url;
      a.download = `baxter_generated_tests_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to generate ZIP archive:', err);
    } finally {
      setIsZipping(false);
    }
  };

  return (
    <section className="baxter-card" style={{ padding: '1.05rem 1.35rem', border: '2px solid #BFDBFE', background: 'linear-gradient(180deg, #FFFFFF 0%, #F0F7FF 100%)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.95rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{ width: 40, height: 40, borderRadius: 8, backgroundColor: '#E0F2FE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Archive size={22} color="#0033A0" />
          </div>
          <div>
            <div className="baxter-card-title" style={{ color: '#002670', fontSize: '1.1rem', marginBottom: '0.15rem' }}>
              Download Generated Test Artifacts (.ZIP)
            </div>
            <p className="baxter-card-subtitle" style={{ marginBottom: 0, fontSize: '0.825rem' }}>
              Includes generated Selenium Python scripts, Cucumber BDD features, and step CSV files from <code>output/tests/</code>.
            </p>
          </div>
        </div>

        <button
          className="btn-run-pipeline"
          onClick={handleDownloadZip}
          disabled={isZipping}
          style={{ background: 'linear-gradient(135deg, #0033A0 0%, #002670 100%)', padding: '0.55rem 1.25rem', fontSize: '0.875rem' }}
        >
          {isZipping ? <Loader2 size={16} className="spin" /> : <Download size={16} />}
          {isZipping ? 'Creating ZIP...' : 'Download Output (.zip)'}
        </button>
      </div>
    </section>
  );
}


