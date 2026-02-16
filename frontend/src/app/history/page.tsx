'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getJobs, createJob, deleteJob, type Job } from '@/lib/api';

/**
 * Format date to a human-readable string
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

/**
 * Get badge styling based on job status
 */
function getStatusBadge(status: string): { text: string; className: string } {
  const normalizedStatus = status.toUpperCase();

  switch (normalizedStatus) {
    case 'QUEUED':
      return {
        text: 'Queued',
        className: 'bg-gray-100 text-gray-800 border-gray-300',
      };
    case 'PROCESSING':
      return {
        text: 'Processing',
        className: 'bg-blue-100 text-blue-800 border-blue-300',
      };
    case 'COMPLETE':
      return {
        text: 'Complete',
        className: 'bg-green-100 text-green-800 border-green-300',
      };
    case 'FAILED':
      return {
        text: 'Failed',
        className: 'bg-danger-light text-danger border-danger/30',
      };
    default:
      return {
        text: status,
        className: 'bg-gray-100 text-gray-800 border-gray-300',
      };
  }
}

export default function HistoryPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reanalysing, setReanalysing] = useState<string | null>(null);

  async function handleReanalyse(job: Job) {
    try {
      setReanalysing(job.id);
      const threshold = parseFloat(localStorage.getItem('confidence_threshold') || '0.5');
      const newJob = await createJob(job.youtube_url, true, threshold);
      router.push(`/sets/${newJob.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reanalyse');
      setReanalysing(null);
    }
  }

  async function handleDelete(job: Job) {
    if (!confirm(`Delete "${job.video_title || 'Untitled'}"? This cannot be undone.`)) return;
    try {
      await deleteJob(job.id);
      setJobs(jobs.filter((j) => j.id !== job.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  }

  useEffect(() => {
    async function fetchJobs() {
      try {
        setLoading(true);
        setError(null);
        const data = await getJobs(1);
        setJobs(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load jobs');
      } finally {
        setLoading(false);
      }
    }

    fetchJobs();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-brick-light py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-carbon mb-8">Processing History</h1>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-paprika"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-brick-light py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-carbon mb-8">Processing History</h1>
          <div className="bg-danger-light border border-danger/30 rounded-lg p-4">
            <p className="text-danger">Error: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="min-h-screen bg-brick-light py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-carbon mb-8">Processing History</h1>
          <div className="bg-sand-light border border-brick rounded-lg p-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
            <p className="text-carbon/70 text-lg">
              No DJ sets processed yet. Submit one to get started!
            </p>
            <Link
              href="/"
              className="inline-block mt-6 px-6 py-3 bg-paprika text-white font-medium rounded-lg hover:bg-saffron transition-colors"
            >
              Submit a DJ Set
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brick-light py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-carbon mb-8">Processing History</h1>
        
        <div className="bg-sand-light border border-brick rounded-lg shadow-sm overflow-hidden">
          <ul className="divide-y divide-brick">
            {jobs.map((job) => {
              const badge = getStatusBadge(job.status);
              const isComplete = job.status.toUpperCase() === 'COMPLETE';

              return (
                <li key={job.id} className="p-6 hover:bg-sand transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0 mr-4">
                      <div className="flex items-center gap-3 mb-2">
                        <h2 className="text-lg font-semibold text-carbon truncate">
                          {job.video_title || 'Untitled'}
                        </h2>
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${badge.className}`}
                        >
                          {badge.text}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-4 text-sm text-carbon/70">
                        <span className="flex items-center">
                          <svg
                            className="h-4 w-4 mr-1"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          {formatDate(job.created_at)}
                        </span>
                        
                        {job.duration_seconds && (
                          <span>
                            {Math.floor(job.duration_seconds / 60)} min
                          </span>
                        )}
                      </div>

                      {job.error_message && (
                        <p className="mt-2 text-sm text-danger">
                          Error: {job.error_message}
                        </p>
                      )}
                    </div>

                    <div className="flex-shrink-0 flex items-center gap-2">
                      {(isComplete || job.status.toUpperCase() === 'FAILED') && (
                        <button
                          onClick={() => handleReanalyse(job)}
                          disabled={reanalysing === job.id}
                          className="inline-flex items-center px-4 py-2 border border-brick text-sm font-medium rounded-md text-carbon bg-sand-light hover:bg-sand transition-colors disabled:opacity-50"
                        >
                          {reanalysing === job.id ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-carbon mr-2"></div>
                              Reanalysing…
                            </>
                          ) : (
                            <>
                              <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                              Reanalyse
                            </>
                          )}
                        </button>
                      )}
                      {isComplete && (
                        <Link
                          href={`/sets/${job.id}`}
                          className="inline-flex items-center px-4 py-2 border border-paprika text-sm font-medium rounded-md text-paprika bg-sand-light hover:bg-sand transition-colors"
                        >
                          View Results
                          <svg
                            className="ml-2 h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 5l7 7-7 7"
                            />
                          </svg>
                        </Link>
                      )}
                      <button
                        onClick={() => handleDelete(job)}
                        className="inline-flex items-center px-4 py-2 border border-danger/30 text-sm font-medium rounded-md text-danger bg-sand-light hover:bg-danger-light transition-colors"
                        title="Delete"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
