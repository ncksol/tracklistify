'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function SettingsPage() {
  const [threshold, setThreshold] = useState(0.5);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const val = localStorage.getItem('confidence_threshold');
    if (val) setThreshold(parseFloat(val));
  }, []);

  function handleSave() {
    localStorage.setItem('confidence_threshold', threshold.toString());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="min-h-screen bg-brick-light py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-carbon mb-8">Settings</h1>

        <div className="bg-sand-light border border-brick rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-carbon mb-1">Confidence Threshold</h2>
          <p className="text-sm text-carbon/60 mb-4">
            Minimum confidence required to accept a track match from ACRCloud.
            Lower values include more matches but may introduce false positives.
          </p>

          <div className="flex items-center gap-4">
            <input
              type="range"
              min="0.2"
              max="1.0"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="flex-grow h-2 bg-brick rounded-lg appearance-none cursor-pointer accent-paprika"
            />
            <span className="flex-shrink-0 w-16 text-right text-lg font-mono font-semibold text-carbon">
              {Math.round(threshold * 100)}%
            </span>
          </div>

          <div className="flex justify-between text-xs text-carbon/50 mt-1 px-1">
            <span>20%</span>
            <span>100%</span>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-paprika text-white text-sm font-medium rounded-lg hover:bg-saffron transition-colors"
            >
              Save
            </button>
            {saved && (
              <span className="text-sm text-saffron font-medium">Settings saved ✓</span>
            )}
          </div>
        </div>

        <div className="mt-6">
          <Link
            href="/"
            className="text-sm text-paprika hover:text-saffron"
          >
            ← Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
