'use client';

import { useEffect, useState, useRef, useCallback, use } from 'react';
import Link from 'next/link';
import {
  getJob,
  getTracklist,
  Job,
  Tracklist,
  Track,
  getJobEvents,
  JobEvent,
  deleteUnidentifiedSegment,
} from '@/lib/api';
import { ProgressBar } from '@/components/ProgressBar';
import { ActivityLog } from '@/components/ActivityLog';
import TrackList from '@/components/TrackList';
import { ExportMenu } from '@/components/ExportMenu';

interface ResultsPageProps {
  params: Promise<{
    id: string;
  }>;
}

type PageState =
  | { type: 'loading' }
  | { type: 'processing'; job: Job }
  | { type: 'complete'; job: Job; tracklist: Tracklist }
  | { type: 'failed'; error: string };

/**
 * Extract YouTube video ID from URL
 */
function extractYouTubeVideoId(url: string): string | null {
  try {
    const urlObj = new URL(url);

    // Handle youtu.be short URLs
    if (urlObj.hostname === 'youtu.be') {
      return urlObj.pathname.slice(1);
    }

    // Handle youtube.com URLs
    if (urlObj.hostname.includes('youtube.com')) {
      return urlObj.searchParams.get('v');
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Format duration in seconds to human-readable format
 */
function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'Unknown';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  }
  return `${minutes}m ${secs}s`;
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const { id: jobId } = use(params);
  const [state, setState] = useState<PageState>({ type: 'loading' });
  const [events, setEvents] = useState<JobEvent[]>([]);
  const youtubeIframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch job data and tracklist
  const fetchData = useCallback(async () => {
    try {
      const job = await getJob(jobId);

      // Check if job is complete
      if (job.status === 'COMPLETE') {
        const tracklist = await getTracklist(jobId);
        setState({ type: 'complete', job, tracklist });
      } else if (job.status === 'FAILED') {
        setState({
          type: 'failed',
          error: job.error_message || 'Job processing failed',
        });
      } else {
        setState({ type: 'processing', job });
      }
    } catch (error) {
      setState({
        type: 'failed',
        error: error instanceof Error ? error.message : 'Failed to load job data',
      });
    }
  }, [jobId]);

  // Initial data fetch
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  // Poll for completion when processing
  useEffect(() => {
    if (state.type !== 'processing') return;

    const interval = setInterval(async () => {
      try {
        const job = await getJob(jobId);

        if (job.status === 'COMPLETE') {
          const tracklist = await getTracklist(jobId);
          setState({ type: 'complete', job, tracklist });
        } else if (job.status === 'FAILED') {
          setState({
            type: 'failed',
            error: job.error_message || 'Job processing failed',
          });
        } else {
          setState({ type: 'processing', job });
        }
      } catch (error) {
        console.error('Failed to poll job status:', error);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [state.type, jobId]);

  // Poll for events when processing
  useEffect(() => {
    if (state.type !== 'processing') return;

    let lastTimestamp: string | undefined;

    const pollEvents = async () => {
      try {
        const newEvents = await getJobEvents(jobId, lastTimestamp);
        if (newEvents.length > 0) {
          setEvents((prev) => [...prev, ...newEvents]);
          const lastEvent = newEvents[newEvents.length - 1];
          if (lastEvent) {
            lastTimestamp = lastEvent.timestamp;
          }
        }
      } catch (error) {
        console.error('Failed to poll events:', error);
      }
    };

    // Initial fetch (all events)
    pollEvents();
    const interval = setInterval(pollEvents, 2000);

    return () => clearInterval(interval);
  }, [state.type, jobId]);

  // Handle track updates
  const handleTrackUpdate = async () => {
    // Refresh tracklist data after update
    if (state.type === 'complete') {
      try {
        const tracklist = await getTracklist(jobId);
        setState({ ...state, tracklist });
      } catch (error) {
        console.error('Failed to refresh tracklist:', error);
      }
    }
  };

  // Handle track deletes
  const handleTrackDelete = async () => {
    // Refresh tracklist data after delete
    if (state.type === 'complete') {
      try {
        const tracklist = await getTracklist(jobId);
        setState({ ...state, tracklist });
      } catch (error) {
        console.error('Failed to refresh tracklist:', error);
      }
    }
  };

  const handleSegmentDelete = async (segmentId: string) => {
    if (state.type === 'complete') {
      try {
        await deleteUnidentifiedSegment(jobId, segmentId);
        const tracklist = await getTracklist(jobId);
        setState({ ...state, tracklist });
      } catch (error) {
        console.error('Failed to delete segment:', error);
      }
    }
  };

  // Handle track clicks - seek YouTube player
  const handleTrackClick = (track: Track) => {
    if (!youtubeIframeRef.current) return;

    const seekSeconds = track.start_time_ms / 1000;

    // Use YouTube iframe API postMessage to seek
    youtubeIframeRef.current.contentWindow?.postMessage(
      JSON.stringify({
        event: 'command',
        func: 'seekTo',
        args: [seekSeconds, true], // seekSeconds, allowSeekAhead
      }),
      '*',
    );
  };

  // Loading state
  if (state.type === 'loading') {
    return (
      <div className="min-h-screen bg-brick-light flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-paprika border-r-transparent"></div>
          <p className="mt-4 text-carbon/70">Loading job data...</p>
        </div>
      </div>
    );
  }

  // Failed state
  if (state.type === 'failed') {
    return (
      <div className="min-h-screen bg-brick-light py-12 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="bg-sand-light rounded-lg shadow-md p-8">
            <div className="flex items-center justify-center mb-6">
              <div className="h-16 w-16 rounded-full bg-danger-light flex items-center justify-center">
                <svg
                  className="h-8 w-8 text-danger"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
            </div>

            <h1 className="text-2xl font-bold text-center text-carbon mb-4">Processing Failed</h1>

            <p className="text-center text-carbon/70 mb-6">{state.error}</p>

            <div className="flex justify-center">
              <Link
                href="/history"
                className="inline-flex items-center px-6 py-3 bg-paprika text-white font-medium rounded-lg hover:bg-saffron transition-colors"
              >
                ← Back
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Processing state
  if (state.type === 'processing') {
    // Get latest progress from events or job data
    const lastEvent = events.length > 0 ? events[events.length - 1] : null;
    const latestProgress = lastEvent?.progress ?? state.job.progress;

    return (
      <div className="min-h-screen bg-brick-light py-12 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="bg-sand-light rounded-lg shadow-md p-8">
            <h1 className="text-2xl font-bold text-carbon mb-2">Processing Tracklist</h1>

            {state.job.video_title && (
              <p className="text-carbon/70 mb-6">{state.job.video_title}</p>
            )}

            <ProgressBar
              status={state.job.status}
              progress={latestProgress}
              error={state.job.error_message}
            />

            <div className="mt-6">
              <ActivityLog events={events} startTime={state.job.created_at} />
            </div>

            <div className="mt-8 pt-6 border-t border-brick">
              <Link
                href="/history"
                className="inline-flex items-center text-paprika hover:text-saffron font-medium"
              >
                ← Back
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Complete state
  const { job, tracklist } = state;
  const trackCount = tracklist.tracks.length;
  const videoId = extractYouTubeVideoId(job.youtube_url);

  return (
    <div className="min-h-screen bg-brick-light py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-sand-light rounded-lg shadow-md p-8 mb-6">
          <div className="flex items-start justify-between gap-4 mb-6">
            <div className="flex-grow">
              <h1 className="text-3xl font-bold text-carbon mb-2">
                {job.video_title || 'Tracklist Results'}
              </h1>

              <div className="flex flex-wrap gap-6 text-sm text-carbon/70">
                <div className="flex items-center gap-2">
                  <svg
                    className="h-5 w-5 text-carbon/50"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span>Duration: {formatDuration(job.duration_seconds)}</span>
                </div>

                <div className="flex items-center gap-2">
                  <svg
                    className="h-5 w-5 text-carbon/50"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                    />
                  </svg>
                  <span>
                    {trackCount} {trackCount === 1 ? 'track' : 'tracks'} identified
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span>Threshold: {Math.round(job.confidence_threshold * 100)}%</span>
                </div>
              </div>
            </div>

            <ExportMenu jobId={jobId} />
          </div>

          <div className="pt-6 border-t border-brick">
            <Link
              href="/history"
              className="inline-flex items-center text-paprika hover:text-saffron font-medium"
            >
              ← Back
            </Link>
          </div>
        </div>

        {/* YouTube Player */}
        {videoId && (
          <div className="bg-sand-light rounded-lg shadow-md overflow-hidden mb-6">
            <div className="aspect-video">
              <iframe
                ref={youtubeIframeRef}
                className="w-full h-full"
                src={`https://www.youtube.com/embed/${videoId}?enablejsapi=1`}
                title="YouTube video player"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            </div>
          </div>
        )}

        {/* Tracklist */}
        <div className="bg-sand-light rounded-lg shadow-md overflow-hidden">
          {trackCount > 0 ? (
            <TrackList
              tracks={tracklist.tracks}
              unidentifiedSegments={tracklist.unidentified_segments}
              onTrackUpdate={handleTrackUpdate}
              onTrackDelete={handleTrackDelete}
              onTrackClick={handleTrackClick}
              onSegmentDelete={handleSegmentDelete}
            />
          ) : (
            <div className="p-12 text-center">
              <svg
                className="mx-auto h-12 w-12 text-carbon/50"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                />
              </svg>
              <p className="mt-4 text-carbon/70">No tracks identified in this set.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
