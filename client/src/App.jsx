import { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [imageFiles, setImageFiles] = useState([]);
  const [enhancements, setEnhancements] = useState([]);
  const [mode, setMode] = useState('pipeline');
  const [enableCompression, setEnableCompression] = useState(false);
  const [compressionPercent, setCompressionPercent] = useState(80);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [resultZipUrl, setResultZipUrl] = useState(null);
  const [error, setError] = useState(null);

  // Handle image file input changes
  const handleImageChange = (e) => {
    setImageFiles([...e.target.files]);
    setResultZipUrl(null);
    setError(null);
  };

  // Toggle enhancements selection
  const toggleEnhancement = (e) => {
    const value = e.target.value;
    setEnhancements((prev) =>
      prev.includes(value) ? prev.filter((f) => f !== value) : [...prev, value]
    );
  };

  // Process the images
  const handleProcess = async () => {
    // Validation checks
    if (!imageFiles.length) {
      setError("Please upload at least one image.");
      return;
    }

    if (!enhancements.length && !enableCompression) {
      setError("Select at least one enhancement or enable compression.");
      return;
    }

    // Prepare form data for submission
    const formData = new FormData();
    imageFiles.forEach((file) => formData.append('images', file));
    formData.append('enhancements', enhancements.join(','));
    formData.append('mode', mode);
    formData.append('compression_enabled', enableCompression.toString());

    if (enableCompression) {
      formData.append('compression_percent', compressionPercent.toString());
    }

    try {
      setProcessing(true);
      setProgress(20);
      setError(null);

      // Send request to server
      const response = await axios.post('http://localhost:8080/process', formData, {
        responseType: 'blob',
        onUploadProgress: (e) => {
          const percent = Math.round((e.loaded * 100) / e.total);
          setProgress(percent < 90 ? percent : 90);
        }
      });

      // Create download URL for the response ZIP file
      const zipUrl = URL.createObjectURL(response.data);
      setResultZipUrl(zipUrl);
      setProgress(100);
    } catch (err) {
      setError(err.response?.data?.error || "Processing failed. Please try again.");
      console.error(err);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="App">
      <h1>Distributed Image Enhancer</h1>
      
      {/* Image input section */}
      <div className="upload-section">
        <h2>Upload Images</h2>
        <input 
          type="file" 
          accept="image/*" 
          multiple 
          onChange={handleImageChange}
          className="file-input" 
        />
        {imageFiles.length > 0 && (
          <p className="file-count">{imageFiles.length} file(s) selected</p>
        )}
      </div>

      {/* Enhancement options */}
      <div className="options-container">
        <fieldset>
          <legend>Choose Enhancements:</legend>
          <div className="checkbox-group">
            <label><input type="checkbox" value="smoothing" onChange={toggleEnhancement} /> Smoothing</label>
            <label><input type="checkbox" value="blackwhite" onChange={toggleEnhancement} /> Black & White</label>
            <label><input type="checkbox" value="clarity" onChange={toggleEnhancement} /> Clarity</label>
            <label><input type="checkbox" value="noise-reduction" onChange={toggleEnhancement} /> Noise Reduction</label>
          </div>
        </fieldset>

        {/* Processing mode selection */}
        <fieldset>
          <legend>Processing Mode:</legend>
          <div className="radio-group">
            <label>
              <input 
                type="radio" 
                name="mode" 
                value="pipeline" 
                checked={mode === 'pipeline'} 
                onChange={(e) => setMode(e.target.value)} 
              /> 
              Pipeline <small>(Apply all filters in sequence)</small>
            </label>
            <label>
              <input 
                type="radio" 
                name="mode" 
                value="independent" 
                checked={mode === 'independent'} 
                onChange={(e) => setMode(e.target.value)} 
              /> 
              Independent <small>(Apply each filter separately)</small>
            </label>
          </div>
        </fieldset>

        {/* Compression settings */}
        <fieldset>
          <legend>Compression:</legend>
          <div className="compression-settings">
            <label className="toggle-switch">
              <input 
                type="checkbox" 
                checked={enableCompression} 
                onChange={(e) => setEnableCompression(e.target.checked)} 
              />
              <span className="slider"></span>
              Enable Compression
            </label>
            
            {enableCompression && (
              <div className="range-slider">
                <input
                  type="range"
                  min="10"
                  max="100"
                  value={compressionPercent}
                  onChange={(e) => setCompressionPercent(parseInt(e.target.value))}
                />
                <p><strong>{compressionPercent}%</strong> Quality</p>
              </div>
            )}
          </div>
        </fieldset>
      </div>

      {/* Error message display */}
      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      {/* Process button */}
      <button 
        className="process-button"
        onClick={handleProcess} 
        disabled={processing}>
        {processing ? 'Processing...' : 'Start Processing'}
      </button>

      {/* Progress bar */}
      {processing && (
        <div className="progress-container">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
          <p>{progress}%</p>
        </div>
      )}

      {/* Download section */}
      {resultZipUrl && (
        <div className="result-section">
          <h3>Download Processed Images</h3>
          <a href={resultZipUrl} download="processed_images.zip" className="download-button">
            Download ZIP
          </a>
        </div>
      )}
    </div>
  );
}

export default App;