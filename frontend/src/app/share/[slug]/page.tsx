'use client';

import { useEffect, useState, use } from 'react';
import Link from 'next/link';
import { getSharedTracklist, Tracklist } from '@/lib/api';
import TrackList from '@/components/TrackList';

interface SharePageProps {
  params: Promise<{
    slug: string;
  }>;
}

type PageState =
  | { type: 'loading' }
  | { type: 'complete'; tracklist: Tracklist }
  | { type: 'not_found' }
  | { type: 'error'; message: string };

/**
 * Public shareable results page
 * Displays a tracklist in read-only mode (no editing capabilities)
 */
export default function SharePage({ params }: SharePageProps) {
  const { slug } = use(params);
  const [state, setState] = useState<PageState>({ type: 'loading' });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const tracklist = await getSharedTracklist(slug);
        setState({ type: 'complete', tracklist });
      } catch (error) {
        if (error instanceof Error) {
          // Check if it's a 404 error
          if (error.message.includes('404')) {
            setState({ type: 'not_found' });
          } else {
            setState({ type: 'error', message: error.message });
          }
        } else {
          setState({ type: 'error', message: 'Failed to load shared tracklist' });
        }
      }
    };

    fetchData();
  }, [slug]);

  // Loading state
  if (state.type === 'loading') {
    return (
      <div className="min-h-screen bg-brick-light flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-paprika border-r-transparent"></div>
          <p className="mt-4 text-carbon/70">Loading shared tracklist...</p>
        </div>
      </div>
    );
  }

  // Not found state
  if (state.type === 'not_found') {
    return (
      <div className="min-h-screen bg-brick-light py-12 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="bg-sand-light rounded-lg shadow-md p-8">
            <div className="flex items-center justify-center mb-6">
              <div className="h-16 w-16 rounded-full bg-brick-light flex items-center justify-center">
                <svg
                  className="h-8 w-8 text-carbon/50"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 12h.01M12 12h.01M12 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
            </div>

            <h1 className="text-2xl font-bold text-center text-carbon mb-4">Tracklist Not Found</h1>

            <p className="text-center text-carbon/70 mb-6">
              The shared tracklist you&apos;re looking for doesn&apos;t exist or has been removed.
            </p>

            <div className="flex justify-center">
              <Link
                href="/"
                className="inline-flex items-center px-6 py-3 bg-paprika text-white font-medium rounded-lg hover:bg-saffron transition-colors"
              >
                Go to Tracklistify
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (state.type === 'error') {
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

            <h1 className="text-2xl font-bold text-center text-carbon mb-4">
              Error Loading Tracklist
            </h1>

            <p className="text-center text-carbon/70 mb-6">{state.message}</p>

            <div className="flex justify-center">
              <Link
                href="/"
                className="inline-flex items-center px-6 py-3 bg-paprika text-white font-medium rounded-lg hover:bg-saffron transition-colors"
              >
                Go to Tracklistify
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Complete state with tracklist data
  const { tracklist } = state;
  const trackCount = tracklist.tracks.length;

  return (
    <div className="min-h-screen bg-brick-light py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-sand-light rounded-lg shadow-md p-8 mb-6">
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-4">
              <svg
                className="h-5 w-5 text-paprika"
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
              <h2 className="text-sm font-semibold text-paprika uppercase tracking-wide">
                Shared Tracklist
              </h2>
            </div>

            <h1 className="text-3xl font-bold text-carbon mb-4">DJ Set Tracklist</h1>

            <div className="flex items-center gap-2 text-sm text-carbon/70">
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
          </div>

          <div className="pt-6 border-t border-brick">
            <Link
              href="/"
              className="inline-flex items-center text-paprika hover:text-saffron font-medium"
            >
              Create your own tracklist on Tracklistify →
            </Link>
          </div>
        </div>

        {/* Tracklist - Read-only mode (no editing props) */}
        <div className="bg-sand-light rounded-lg shadow-md overflow-hidden">
          {trackCount > 0 ? (
            <TrackList
              tracks={tracklist.tracks}
              unidentifiedSegments={tracklist.unidentified_segments}
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
