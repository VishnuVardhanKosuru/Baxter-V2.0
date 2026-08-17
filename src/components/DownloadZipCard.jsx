import React, { useState } from 'react';
import { Archive, Download, Loader2 } from 'lucide-react';

export default function DownloadZipCard() {
  const [isZipping, setIsZipping] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  const handleDownloadZip = async () => {
    setIsZipping(true);
    setDownloadError('');
    try {
      // Direct streaming download of generated test suite from backend /api/download-zip
      const res = await fetch('/api/download-zip');
      if (!res.ok) {
        throw new Error(
          res.status === 404
            ? 'No generated test files are available yet. Run the pipeline first.'
            : `Download failed with status ${res.status}.`,
        );
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `baxter_generated_tests_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download ZIP archive:', err);
      setDownloadError(err.message || 'Could not download test artifacts ZIP.');
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

      {downloadError && (
        <div style={{
          marginTop: '0.85rem',
          padding: '0.6rem 0.9rem',
          backgroundColor: '#FEF2F2',
          border: '1px solid #FCA5A5',
          color: '#991B1B',
          borderRadius: 8,
          fontSize: '0.825rem',
        }}>
          {downloadError}
        </div>
      )}
    </section>
  );
}


