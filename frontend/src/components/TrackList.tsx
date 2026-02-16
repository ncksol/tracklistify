'use client';

import { useState } from 'react';
import { Track, UnidentifiedSegment, createTrack } from '@/lib/api';
import TrackRow from './TrackRow';

interface TrackListProps {
  tracks: Track[];
  unidentifiedSegments: UnidentifiedSegment[];
  onTrackUpdate?: (track: Track) => void;
  onTrackDelete?: (trackId: string) => void;
  onTrackCreate?: (track: Track) => void;
  onTrackClick?: (track: Track) => void;
  onSegmentDelete?: (segmentId: string) => void;
}

type ListItem = { type: 'track'; data: Track } | { type: 'gap'; data: UnidentifiedSegment };

/**
 * Format milliseconds to MM:SS or HH:MM:SS
 */
function formatTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/**
 * Inline form for adding a track to an unidentified segment
 */
interface GapEditFormProps {
  segment: UnidentifiedSegment;
  isCreating: boolean;
  onSave: (data: {
    artist: string;
    title: string;
    start_time_ms: number;
    end_time_ms: number;
  }) => void;
  onCancel: () => void;
}

function GapEditForm({ segment, isCreating, onSave, onCancel }: GapEditFormProps) {
  const [artist, setArtist] = useState('');
  const [title, setTitle] = useState('');
  const [startTime, setStartTime] = useState(segment.start_time_ms);
  const [endTime, setEndTime] = useState(segment.end_time_ms);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!artist.trim() || !title.trim()) {
      alert('Artist and Title are required');
      return;
    }
    onSave({ artist, title, start_time_ms: startTime, end_time_ms: endTime });
  };

  return (
    <div className="px-4 py-3 border-b border-brick bg-sand-light">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor={`artist-${segment.id}`}
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Artist
            </label>
            <input
              id={`artist-${segment.id}`}
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              disabled={isCreating}
              className="w-full px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika disabled:bg-brick-light"
              placeholder="Artist name"
            />
          </div>
          <div>
            <label
              htmlFor={`title-${segment.id}`}
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Title
            </label>
            <input
              id={`title-${segment.id}`}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isCreating}
              className="w-full px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika disabled:bg-brick-light"
              placeholder="Track title"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor={`start-${segment.id}`}
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Start Time (ms)
            </label>
            <input
              id={`start-${segment.id}`}
              type="number"
              value={startTime}
              onChange={(e) => setStartTime(Number(e.target.value))}
              disabled={isCreating}
              className="w-full px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika disabled:bg-brick-light"
            />
          </div>
          <div>
            <label
              htmlFor={`end-${segment.id}`}
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              End Time (ms)
            </label>
            <input
              id={`end-${segment.id}`}
              type="number"
              value={endTime}
              onChange={(e) => setEndTime(Number(e.target.value))}
              disabled={isCreating}
              className="w-full px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika disabled:bg-brick-light"
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isCreating}
            className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isCreating}
            className="px-3 py-1 text-sm font-medium text-white bg-blue-600 border border-blue-600 rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isCreating ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
}

/**
 * TrackList Component
 *
 * Displays a sorted list of tracks and unidentified segments with a header row.
 * Combines both types of items and sorts them by start_time_ms.
 */
export default function TrackList({
  tracks,
  unidentifiedSegments,
  onTrackUpdate,
  onTrackDelete,
  onTrackCreate,
  onTrackClick,
  onSegmentDelete,
}: TrackListProps) {
  const [editingGapId, setEditingGapId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  // Combine tracks and unidentified segments into a single sorted list
  const combinedItems: ListItem[] = [
    ...tracks.map((track): ListItem => ({ type: 'track', data: track })),
    ...unidentifiedSegments.map((segment): ListItem => ({ type: 'gap', data: segment })),
  ].sort((a, b) => {
    const aStartTime = a.type === 'track' ? a.data.start_time_ms : a.data.start_time_ms;
    const bStartTime = b.type === 'track' ? b.data.start_time_ms : b.data.start_time_ms;
    return aStartTime - bStartTime;
  });

  const handleAddTrack = async (
    segment: UnidentifiedSegment,
    formData: { artist: string; title: string; start_time_ms: number; end_time_ms: number },
  ) => {
    if (!segment.job_id) return;

    setIsCreating(true);
    try {
      // Calculate position based on start time
      const position = tracks.filter((t) => t.start_time_ms < formData.start_time_ms).length + 1;

      const newTrack = await createTrack(segment.job_id, {
        position,
        start_time_ms: formData.start_time_ms,
        end_time_ms: formData.end_time_ms,
        title: formData.title,
        artist: formData.artist,
      });

      onTrackCreate?.(newTrack);
      setEditingGapId(null);
    } catch (error) {
      console.error('Failed to create track:', error);
      alert(error instanceof Error ? error.message : 'Failed to create track');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="w-full">
      {/* Header Row */}
      <div className="flex items-center gap-4 px-4 py-2 bg-brick-light border-b border-brick">
        <div className="flex-shrink-0 w-12 text-left text-xs font-semibold text-carbon/70 uppercase">
          #
        </div>
        <div className="flex-shrink-0 w-20 text-left text-xs font-semibold text-carbon/70 uppercase">
          Time
        </div>
        <div className="flex-grow text-left text-xs font-semibold text-carbon/70 uppercase">
          Track
        </div>
        <div className="flex-shrink-0 text-left text-xs font-semibold text-carbon/70 uppercase">
          Confidence
        </div>
      </div>

      {/* List Items */}
      <div>
        {combinedItems.map((item) => {
          if (item.type === 'track') {
            return (
              <TrackRow
                key={`track-${item.data.id}`}
                track={item.data}
                onUpdate={onTrackUpdate}
                onDelete={onTrackDelete}
                onClick={onTrackClick}
              />
            );
          } else {
            // Render unidentified segment gap
            const segment = item.data;
            const isEditing = editingGapId === segment.id;

            if (isEditing) {
              return (
                <GapEditForm
                  key={`gap-${segment.id}`}
                  segment={segment}
                  isCreating={isCreating}
                  onSave={(formData) => handleAddTrack(segment, formData)}
                  onCancel={() => setEditingGapId(null)}
                />
              );
            }

            return (
              <div
                key={`gap-${segment.id}`}
                className="flex items-center gap-4 px-4 py-3 border-b border-dashed border-brick bg-brick-light"
              >
                {/* Empty position column */}
                <div className="flex-shrink-0 w-12" />

                {/* Timestamp Range */}
                <div className="flex-shrink-0 w-20 text-sm font-mono text-gray-400">
                  {formatTimestamp(segment.start_time_ms)}
                </div>

                {/* Unidentified Label with time range */}
                <div className="flex-grow min-w-0 text-sm text-gray-400 italic">
                  <span className="truncate">
                    Unidentified ({formatTimestamp(segment.start_time_ms)} —{' '}
                    {formatTimestamp(segment.end_time_ms)})
                  </span>
                </div>

                {/* Empty confidence column */}
                <div className="flex-shrink-0 text-sm text-gray-400">—</div>

                {/* Add Track Button */}
                <div className="flex-shrink-0 flex gap-2">
                  <button
                    onClick={() => setEditingGapId(segment.id)}
                    className="px-3 py-1 text-xs font-medium text-paprika bg-sand-light border border-paprika/30 rounded hover:bg-sand transition-colors"
                  >
                    Add Track
                  </button>
                  {onSegmentDelete && (
                    <button
                      onClick={() => onSegmentDelete(segment.id)}
                      className="px-3 py-1 text-xs font-medium text-danger bg-danger-light border border-danger/30 rounded hover:bg-danger/10 transition-colors"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            );
          }
        })}
      </div>
    </div>
  );
}
