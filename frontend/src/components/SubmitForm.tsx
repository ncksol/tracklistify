'use client';

import { useState } from 'react';
import { createJob } from '@/lib/api';

interface SubmitFormProps {
  onJobCreated: (jobId: string) => void;
}

/**
 * Validates if the URL is a valid YouTube URL
 */
function isValidYouTubeUrl(url: string): boolean {
  try {
    const urlObj = new URL(url);
    return (
      urlObj.hostname === 'www.youtube.com' ||
      urlObj.hostname === 'youtube.com' ||
      urlObj.hostname === 'youtu.be'
    );
  } catch {
    return false;
  }
}

export default function SubmitForm({ onJobCreated }: SubmitFormProps) {
  const [url, setUrl] = useState('');
  const [cookieFile, setCookieFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.name.endsWith('.txt')) {
        setCookieFile(null);
        setError('Please select a .txt file');
        e.target.value = ''; // Clear the input
        return;
      }
      setCookieFile(file);
      setError(null);
    } else {
      setCookieFile(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!url.trim()) {
      setError('Please enter a YouTube URL');
      return;
    }

    if (!isValidYouTubeUrl(url)) {
      setError('Please enter a valid YouTube URL (youtube.com or youtu.be)');
      return;
    }

    setIsLoading(true);

    try {
      const threshold = parseFloat(localStorage.getItem('confidence_threshold') || '0.5');
      const job = await createJob(url, false, threshold, cookieFile || undefined);
      onJobCreated(job.id);
      setUrl(''); // Clear input on success
      setCookieFile(null); // Clear file on success
      // Reset file input
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste a YouTube DJ set URL..."
            disabled={isLoading}
            className="w-full px-4 py-3 text-lg text-carbon border border-brick rounded-lg focus:ring-2 focus:ring-paprika focus:border-transparent disabled:bg-brick-light disabled:cursor-not-allowed placeholder:text-carbon/40"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-carbon mb-2">Cookies (optional)</label>
          <input
            type="file"
            accept=".txt"
            onChange={handleFileChange}
            disabled={isLoading}
            className="w-full px-4 py-2 text-sm text-carbon border border-brick rounded-lg file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-paprika file:text-white hover:file:bg-saffron file:cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
          />
          {cookieFile && <p className="mt-1 text-xs text-carbon/60">Selected: {cookieFile.name}</p>}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-paprika hover:bg-saffron text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:bg-paprika/60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <svg
                className="animate-spin h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Processing...
            </>
          ) : (
            'Identify Tracks'
          )}
        </button>
      </form>

      {error && (
        <div className="mt-4 p-3 bg-danger-light border border-danger/30 rounded-lg">
          <p className="text-danger text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}
