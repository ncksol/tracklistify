'use client';

import { useState, useRef, useEffect } from 'react';

interface ExportMenuProps {
  jobId: string;
}

export function ExportMenu({ jobId }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showCopied, setShowCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleExport = async (format: 'text' | 'json') => {
    try {
      const response = await fetch(`${apiUrl}/api/jobs/${jobId}/export?format=${format}`);

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tracklist-${jobId}.${format === 'text' ? 'txt' : 'json'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setIsOpen(false);
    } catch (error) {
      console.error('Export error:', error);
      alert('Failed to export. Please try again.');
    }
  };

  const handleShareLink = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/jobs/${jobId}/share`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Share link creation failed: ${response.statusText}`);
      }

      const data = await response.json();
      const shareUrl = data.url || data.shareUrl || `${window.location.origin}/share/${jobId}`;

      // Copy to clipboard
      await navigator.clipboard.writeText(shareUrl);

      // Show feedback
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 2000);

      setIsOpen(false);
    } catch (error) {
      console.error('Share link error:', error);
      alert('Failed to create share link. Please try again.');
    }
  };

  return (
    <div className="relative" ref={menuRef}>
      {/* Export Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-10 items-center justify-center gap-2 rounded-lg bg-paprika px-4 text-sm font-medium text-white transition-colors hover:bg-saffron focus:outline-none focus:ring-2 focus:ring-paprika focus:ring-offset-2"
      >
        Export
        <svg
          className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 z-10 mt-2 w-56 rounded-lg border border-brick bg-sand-light shadow-lg dark:border-carbon dark:bg-carbon">
          <div className="py-1">
            <button
              onClick={() => handleExport('text')}
              className="flex w-full items-center px-4 py-2 text-sm text-carbon transition-colors hover:bg-sand dark:text-sand-light dark:hover:bg-carbon"
            >
              <svg
                className="mr-3 h-5 w-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Plain Text (.txt)
            </button>

            <button
              onClick={() => handleExport('json')}
              className="flex w-full items-center px-4 py-2 text-sm text-carbon transition-colors hover:bg-sand dark:text-sand-light dark:hover:bg-carbon"
            >
              <svg
                className="mr-3 h-5 w-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                />
              </svg>
              JSON (.json)
            </button>

            <div className="my-1 border-t border-brick dark:border-carbon" />

            <button
              onClick={handleShareLink}
              className="flex w-full items-center px-4 py-2 text-sm text-carbon transition-colors hover:bg-sand dark:text-sand-light dark:hover:bg-carbon"
            >
              <svg
                className="mr-3 h-5 w-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
                />
              </svg>
              Copy Share Link
            </button>
          </div>
        </div>
      )}

      {/* Copied Feedback */}
      {showCopied && (
        <div className="absolute right-0 top-12 z-20 mt-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm font-medium text-green-800 shadow-lg dark:border-green-800 dark:bg-green-900 dark:text-green-200">
          ✓ Copied!
        </div>
      )}
    </div>
  );
}
