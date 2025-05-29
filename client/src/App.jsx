import { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [imageFile, setImageFile] = useState(null);
  const [filter, setFilter] = useState('average');
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [resultImageUrl, setResultImageUrl] = useState(null);

  // Handle image input change
  const handleImageChange = (e) => {
    setImageFile(e.target.files[0]);
    setResultImageUrl(null); // Reset result when new image is uploaded
  };

  // Handle filter change
  const handleFilterChange = (e) => {
    setFilter(e.target.value);
  };

  // Upload and process image
  const handleProcessImage = async () => {
    if (!imageFile) {
      alert("Please upload an image first.");
      return;
    }

    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('filter', filter);

    try {
      setProcessing(true);
      setProgress(30); // Fake progress step 1

      const response = await axios.post(
        'http://localhost:8080/process',
        formData,
        {
          responseType: 'blob', // We'll get back an image
          onUploadProgress: (e) => {
            const percent = Math.round((e.loaded * 100) / e.total);
            setProgress(percent < 90 ? percent : 90); // Cap at 90% until response
          }
        }
      );

      // Step 3: Convert image blob to URL
      const imageUrl = URL.createObjectURL(response.data);
      setResultImageUrl(imageUrl);
      setProgress(100);
    } catch (error) {
      console.error("Image processing failed:", error);
      alert("Image processing failed.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="App">
      <h1>Distributed Image Processing</h1>

      {/* Image Upload */}
      <input type="file" accept="image/*" onChange={handleImageChange} />

      {/* Filter Selection */}
      <select value={filter} onChange={handleFilterChange}>
        <option value="average">Averaging Filter</option>
        {/* Future filters can be added here */}
      </select>

      {/* Process Button */}
      <button onClick={handleProcessImage} disabled={processing}>
        {processing ? 'Processing...' : 'Process'}
      </button>

      {/* Progress Bar */}
      {processing && (
        <div style={{ width: '300px', marginTop: '1rem' }}>
          <div style={{
            height: '20px',
            width: `${progress}%`,
            backgroundColor: '#4caf50',
            transition: 'width 0.3s ease'
          }} />
          <p>{progress}%</p>
        </div>
      )}

      {/* Result Display */}
      {resultImageUrl && (
        <div style={{ marginTop: '2rem' }}>
          <h3>Processed Image:</h3>
          <img src={resultImageUrl} alt="Processed" style={{ maxWidth: '500px' }} />
          <br />
          <a href={resultImageUrl} download="processed.jpg">
            <button>Download Image</button>
          </a>
        </div>
      )}
    </div>
  );
}

export default App;
