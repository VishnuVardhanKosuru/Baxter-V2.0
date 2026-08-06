import React, { useRef } from 'react';
import { FileText, Play, UploadCloud, X, CheckCircle2 } from 'lucide-react';

export default function InputSection({
  frdFile,
  setFrdFile,
  excelFile,
  setExcelFile,
  pipelineState,
  onRunPipeline
}) {
  const frdInputRef = useRef(null);
  const excelInputRef = useRef(null);

  const handleFrdUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFrdFile({
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        type: file.type || 'Word Document (.docx)',
        rawFile: file,
        useSample: false
      });
    }
  };

  const handleExcelUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setExcelFile({
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        type: file.type || 'Word Document (.docx)',
        rawFile: file,
        useSample: false
      });
    }
  };

  const handleUseSampleFiles = () => {
    setFrdFile({
      name: 'ShopSphere_Functional_Requirements_Document.docx',
      size: '23.8 KB',
      type: 'Sample FRD (.docx)',
      rawFile: null,
      useSample: true
    });
    setExcelFile({
      name: 'ShopSphere_Manual_Testcases.docx',
      size: '11.5 KB',
      type: 'Sample Test Cases (.docx)',
      rawFile: null,
      useSample: true
    });
  };

  const isReadyToRun = pipelineState !== 'running';

  const handleRunClick = () => {
    if (!frdFile || !excelFile) {
      handleUseSampleFiles();
    }
    onRunPipeline();
  };

  return (
    <section className="baxter-card" style={{ padding: '1.05rem 1.35rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.85rem', marginBottom: '0.85rem' }}>
        <div>
          <div className="baxter-card-title" style={{ fontSize: '1.1rem', marginBottom: '0.15rem' }}>
            <UploadCloud size={20} className="text-baxter-blue" />
            Requirement &amp; Test Ingestion
          </div>
          <p className="baxter-card-subtitle" style={{ marginBottom: 0, fontSize: '0.825rem' }}>
            Upload your FRD document and manual test cases (.docx) to parse into the <code>output/</code> folder.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center' }}>
          <button
            type="button"
            className="sample-btn"
            disabled={pipelineState === 'running'}
            onClick={handleUseSampleFiles}
            style={{ padding: '0.55rem 1rem', fontSize: '0.825rem' }}
          >
            <CheckCircle2 size={15} style={{ display: 'inline', marginRight: 5 }} />
            Load Sample ShopSphere Files
          </button>

          <button
            className="btn-run-pipeline"
            disabled={!isReadyToRun}
            onClick={handleRunClick}
            style={{ padding: '0.55rem 1.25rem', fontSize: '0.875rem' }}
          >
            <Play size={16} fill="currentColor" />
            {pipelineState === 'running' ? 'Evaluating & Parsing...' : 'Evaluate'}
          </button>
        </div>
      </div>

      {/* Upload Cards Grid */}
      <div className="upload-grid" style={{ marginBottom: 0, gap: '1rem' }}>
        {/* FRD Document Upload Card */}
        <div>
          <input
            type="file"
            ref={frdInputRef}
            onChange={handleFrdUpload}
            accept=".docx,.doc"
            style={{ display: 'none' }}
          />

          {!frdFile ? (
            <div
              className="upload-zone"
              onClick={() => frdInputRef.current.click()}
              style={{ minHeight: '110px', padding: '0.85rem 1rem' }}
            >
              <FileText className="upload-icon" style={{ width: 28, height: 28, marginBottom: '0.35rem' }} />
              <div className="upload-label" style={{ fontSize: '0.9rem' }}>Upload FRD Document</div>
              <div className="upload-hint" style={{ fontSize: '0.775rem', marginBottom: '0.4rem' }}>Supports Word (.docx) format</div>
              <button
                type="button"
                className="sample-btn"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                onClick={(e) => {
                  e.stopPropagation();
                  frdInputRef.current.click();
                }}
              >
                <UploadCloud size={13} style={{ display: 'inline', marginRight: 5 }} />
                Browse &amp; Upload FRD
              </button>
            </div>
          ) : (
            <div className="uploaded-file-card" style={{ padding: '0.95rem 1.15rem' }}>
              <div className="file-info">
                <FileText size={22} color="#0033A0" />
                <div>
                  <div className="file-name" style={{ fontSize: '0.9rem' }}>{frdFile.name}</div>
                  <div className="file-meta" style={{ fontSize: '0.775rem' }}>
                    {frdFile.size} • {frdFile.type}
                  </div>
                </div>
              </div>
              <button
                className="remove-file-btn"
                title="Remove file"
                disabled={pipelineState === 'running'}
                onClick={() => setFrdFile(null)}
              >
                <X size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Manual Test Cases Upload Card */}
        <div>
          <input
            type="file"
            ref={excelInputRef}
            onChange={handleExcelUpload}
            accept=".docx,.doc"
            style={{ display: 'none' }}
          />

          {!excelFile ? (
            <div
              className="upload-zone"
              onClick={() => excelInputRef.current.click()}
              style={{ minHeight: '110px', padding: '0.85rem 1rem' }}
            >
              <FileText className="upload-icon" style={{ width: 28, height: 28, marginBottom: '0.35rem' }} />
              <div className="upload-label" style={{ fontSize: '0.9rem' }}>Upload Manual Test Cases</div>
              <div className="upload-hint" style={{ fontSize: '0.775rem', marginBottom: '0.4rem' }}>Supports Word (.docx) format</div>
              <button
                type="button"
                className="sample-btn"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                onClick={(e) => {
                  e.stopPropagation();
                  excelInputRef.current.click();
                }}
              >
                <UploadCloud size={13} style={{ display: 'inline', marginRight: 5 }} />
                Browse &amp; Upload Manual Test Cases
              </button>
            </div>
          ) : (
            <div className="uploaded-file-card" style={{ padding: '0.95rem 1.15rem' }}>
              <div className="file-info">
                <FileText size={22} color="#0033A0" />
                <div>
                  <div className="file-name" style={{ fontSize: '0.9rem' }}>{excelFile.name}</div>
                  <div className="file-meta" style={{ fontSize: '0.775rem' }}>
                    {excelFile.size} • {excelFile.type}
                  </div>
                </div>
              </div>
              <button
                className="remove-file-btn"
                title="Remove file"
                disabled={pipelineState === 'running'}
                onClick={() => setExcelFile(null)}
              >
                <X size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

