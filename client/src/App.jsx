import { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [imageFiles, setImageFiles] = useState([]);
  const [selectedFilters, setSelectedFilters] = useState([]);
  const [mode, setMode] = useState('pipeline'); // pipeline or independent
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [resultZipUrl, setResultZipUrl] = useState(null);

  const handleImageChange = (e) => {
    setImageFiles([...e.target.files]);
    setResultZipUrl(null);
  };

  const handleFilterToggle = (e) => {
    const value = e.target.value;
    setSelectedFilters((prev) =>
      prev.includes(value) ? prev.filter((f) => f !== value) : [...prev, value]
    );
  };

  const handleModeChange = (e) => {
    setMode(e.target.value);
  };

  const handleProcessImages = async () => {
    if (!imageFiles.length) {
      alert("Please upload at least one image.");
      return;
    }
    if (!selectedFilters.length) {
      alert("Please select at least one filter.");
      return;
    }

    const formData = new FormData();
    imageFiles.forEach((file) => formData.append('images', file));
    formData.append('filters', selectedFilters.join(','));
    formData.append('mode', mode);

    try {
      setProcessing(true);
      setProgress(30);

      const response = await axios.post('http://localhost:8080/process', formData, {
        responseType: 'blob',
        onUploadProgress: (e) => {
          const percent = Math.round((e.loaded * 100) / e.total);
          setProgress(percent < 90 ? percent : 90);
        }
      });

      const zipUrl = URL.createObjectURL(response.data);
      setResultZipUrl(zipUrl);
      setProgress(100);
    } catch (err) {
      console.error("Processing failed:", err);
      alert("Image processing failed.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="App">
      <h1>Distributed Image Processing</h1>

      <input type="file" accept="image/*" multiple onChange={handleImageChange} />

      <fieldset>
        <legend>Select Filters:</legend>
        <label><input type="checkbox" value="average" onChange={handleFilterToggle} /> Averaging</label><br />
        <label><input type="checkbox" value="grayscale" onChange={handleFilterToggle} /> Grayscale</label><br />
        <label><input type="checkbox" value="sharpen" onChange={handleFilterToggle} /> Sharpen</label><br />
        <label><input type="checkbox" value="denoise" onChange={handleFilterToggle} /> Denoise</label>
      </fieldset>

      <fieldset>
        <legend>Processing Mode:</legend>
        <label><input type="radio" name="mode" value="pipeline" checked={mode === 'pipeline'} onChange={handleModeChange} /> Pipeline (all filters sequentially)</label><br />
        <label><input type="radio" name="mode" value="independent" checked={mode === 'independent'} onChange={handleModeChange} /> Independent (each filter separately)</label>
      </fieldset>

      <button onClick={handleProcessImages} disabled={processing}>
        {processing ? 'Processing...' : 'Process'}
      </button>

      {processing && (
        <div style={{ width: '300px', marginTop: '1rem' }}>
          <div style={{ height: '20px', width: `${progress}%`, backgroundColor: '#4caf50', transition: 'width 0.3s ease' }} />
          <p>{progress}%</p>
        </div>
      )}

      {resultZipUrl && (
        <div style={{ marginTop: '2rem' }}>
          <h3>Download Results:</h3>
          <a href={resultZipUrl} download="processed_images.zip">
            <button>Download ZIP</button>
          </a>
        </div>
      )}
    </div>
  );
}

export default App;
