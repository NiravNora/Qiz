import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState('');

  // Poll job status
  useEffect(() => {
    if (!jobId || !isGenerating) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/job-status/${jobId}`);
        setJobStatus(response.data);

        if (response.data.status === 'completed' || response.data.status === 'error') {
          setIsGenerating(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Error fetching job status:', err);
        setError('Failed to fetch job status');
        setIsGenerating(false);
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, isGenerating]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!topic.trim()) {
      setError('Please enter a topic name');
      return;
    }

    setError('');
    setIsGenerating(true);
    setJobStatus(null);

    try {
      const response = await axios.post(`${BACKEND_URL}/api/generate-mcq-pdf`, {
        topic: topic.trim()
      });

      setJobId(response.data.job_id);
      setJobStatus(response.data);
    } catch (err) {
      console.error('Error starting MCQ generation:', err);
      setError(err.response?.data?.detail || 'Failed to start MCQ generation');
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    if (jobStatus?.pdf_url) {
      window.open(`${BACKEND_URL}${jobStatus.pdf_url}`, '_blank');
    }
  };

  const resetForm = () => {
    setTopic('');
    setIsGenerating(false);
    setJobId(null);
    setJobStatus(null);
    setError('');
  };

  const getProgressPercentage = () => {
    if (!jobStatus || jobStatus.total_links === 0) return 0;
    return Math.round((jobStatus.processed_links / jobStatus.total_links) * 100);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              Testbook MCQ Extractor
            </h1>
            <p className="text-gray-600">
              Extract MCQs from Testbook and generate a professional PDF
            </p>
          </div>

          {/* Main Card */}
          <div className="bg-white rounded-xl shadow-lg p-8">
            {/* Input Form */}
            <form onSubmit={handleSubmit} className="mb-6">
              <div className="mb-4">
                <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-2">
                  Enter Topic Name:
                </label>
                <input
                  type="text"
                  id="topic"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., Heart, Physics, Biology"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition duration-200"
                  disabled={isGenerating}
                />
              </div>

              <button
                type="submit"
                disabled={!topic.trim() || isGenerating}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-lg transition duration-200 flex items-center justify-center"
              >
                {isGenerating ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Generating PDF...
                  </>
                ) : (
                  'Generate PDF'
                )}
              </button>
            </form>

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-700">{error}</p>
              </div>
            )}

            {/* Status Display */}
            {jobStatus && (
              <div className="border-t pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Progress Status</h3>
                
                {/* Progress Bar */}
                {isGenerating && jobStatus.total_links > 0 && (
                  <div className="mb-4">
                    <div className="flex justify-between text-sm text-gray-600 mb-1">
                      <span>Processing Links</span>
                      <span>{getProgressPercentage()}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${getProgressPercentage()}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {/* Status Info */}
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Status:</span>
                    <span className={`font-medium ${
                      jobStatus.status === 'completed' ? 'text-green-600' :
                      jobStatus.status === 'error' ? 'text-red-600' :
                      'text-blue-600'
                    }`}>
                      {jobStatus.status === 'completed' ? 'Completed' :
                       jobStatus.status === 'error' ? 'Error' :
                       'Processing'}
                    </span>
                  </div>
                  
                  <div className="flex justify-between">
                    <span className="text-gray-600">Progress:</span>
                    <span className="text-gray-900">{jobStatus.progress}</span>
                  </div>

                  {jobStatus.total_links > 0 && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Links Found:</span>
                        <span className="text-gray-900">{jobStatus.total_links}</span>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-gray-600">Links Processed:</span>
                        <span className="text-gray-900">{jobStatus.processed_links}/{jobStatus.total_links}</span>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-gray-600">MCQs Found:</span>
                        <span className="text-gray-900 font-semibold">{jobStatus.mcqs_found}</span>
                      </div>
                    </>
                  )}
                </div>

                {/* Download Button */}
                {jobStatus.status === 'completed' && jobStatus.pdf_url && (
                  <div className="mt-6 space-y-3">
                    <button
                      onClick={handleDownload}
                      className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition duration-200 flex items-center justify-center"
                    >
                      <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                      Download PDF
                    </button>
                    
                    <button
                      onClick={resetForm}
                      className="w-full bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 px-6 rounded-lg transition duration-200"
                    >
                      Generate Another PDF
                    </button>
                  </div>
                )}

                {/* Error Reset */}
                {jobStatus.status === 'error' && (
                  <div className="mt-4">
                    <button
                      onClick={resetForm}
                      className="w-full bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 px-6 rounded-lg transition duration-200"
                    >
                      Try Again
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="text-center mt-8 text-gray-600">
            <p className="text-sm">
              This tool searches Testbook using Google Custom Search API and extracts MCQ content for educational purposes.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;