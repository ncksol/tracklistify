'use client';

import { useState } from 'react';
import { Track, updateTrack, deleteTrack } from '@/lib/api';

interface TrackRowProps {
  track: Track;
  onUpdate?: (track: Track) => void;
  onDelete?: (trackId: string) => void;
  onClick?: (track: Track) => void;
}

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
 * Get confidence badge color classes based on confidence score
 */
function getConfidenceBadgeClasses(score: number | null): string {
  if (score === null) {
    return 'bg-gray-100 text-gray-600';
  }

  const percentage = score * 100;

  if (percentage > 80) {
    return 'bg-green-100 text-green-700';
  }

  if (percentage >= 60) {
    return 'bg-yellow-100 text-yellow-700';
  }

  return 'bg-danger-light text-danger';
}

/**
 * Parse timestamp string (MM:SS or HH:MM:SS) to milliseconds
 */
function parseTimestamp(timestamp: string): number | null {
  const parts = timestamp.split(':').map(Number);
  
  if (parts.some(isNaN)) {
    return null;
  }
  
  if (parts.length === 2) {
    // MM:SS
    const minutes = parts[0];
    const seconds = parts[1];
    if (minutes === undefined || seconds === undefined) {
      return null;
    }
    return (minutes * 60 + seconds) * 1000;
  } else if (parts.length === 3) {
    // HH:MM:SS
    const hours = parts[0];
    const minutes = parts[1];
    const seconds = parts[2];
    if (hours === undefined || minutes === undefined || seconds === undefined) {
      return null;
    }
    return (hours * 3600 + minutes * 60 + seconds) * 1000;
  }
  
  return null;
}

/**
 * TrackRow Component
 * 
 * Displays a single track in the tracklist with position, timestamp, title/artist,
 * confidence score, and transition indicator. Supports inline editing and deletion.
 */
export default function TrackRow({ track, onUpdate, onDelete, onClick }: TrackRowProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Edit form state
  const [editArtist, setEditArtist] = useState(track.artist || '');
  const [editTitle, setEditTitle] = useState(track.title || '');
  const [editStartTime, setEditStartTime] = useState(formatTimestamp(track.start_time_ms));
  
  const isUnidentified = !track.title && !track.artist;
  const displayText = isUnidentified
    ? 'Unidentified'
    : `${track.artist || 'Unknown Artist'} — ${track.title || 'Unknown Title'}`;

  const handleEditClick = () => {
    setEditArtist(track.artist || '');
    setEditTitle(track.title || '');
    setEditStartTime(formatTimestamp(track.start_time_ms));
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleSaveEdit = async () => {
    if (!track.job_id) {
      console.error('Cannot update track: job_id is missing');
      return;
    }

    const startTimeMs = parseTimestamp(editStartTime);
    
    if (startTimeMs === null) {
      alert('Invalid time format. Use MM:SS or HH:MM:SS');
      return;
    }

    setIsLoading(true);
    
    try {
      const updatedTrack = await updateTrack(track.job_id, track.id, {
        artist: editArtist || null,
        title: editTitle || null,
        start_time_ms: startTimeMs,
      });
      
      setIsEditing(false);
      
      if (onUpdate) {
        onUpdate(updatedTrack);
      }
    } catch (error) {
      console.error('Failed to update track:', error);
      alert(`Failed to update track: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteClick = () => {
    setIsDeleting(true);
  };

  const handleCancelDelete = () => {
    setIsDeleting(false);
  };

  const handleConfirmDelete = async () => {
    if (!track.job_id) {
      console.error('Cannot delete track: job_id is missing');
      return;
    }

    setIsLoading(true);
    
    try {
      await deleteTrack(track.job_id, track.id);
      
      if (onDelete) {
        onDelete(track.id);
      }
    } catch (error) {
      console.error('Failed to delete track:', error);
      alert(`Failed to delete track: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsDeleting(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-brick hover:bg-sand-light transition-colors">
      {/* Position Number */}
      <div className="flex-shrink-0 w-12 text-left text-sm font-medium text-carbon">
        {track.position}
      </div>

      {isEditing ? (
        <>
          {/* Edit Mode */}
          <div className="flex-shrink-0 w-20">
            <input
              type="text"
              value={editStartTime}
              onChange={(e) => setEditStartTime(e.target.value)}
              className="w-full px-2 py-1 text-sm font-mono border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika"
              placeholder="MM:SS"
              disabled={isLoading}
            />
          </div>

          <div className="flex-grow min-w-0 flex gap-2">
            <input
              type="text"
              value={editArtist}
              onChange={(e) => setEditArtist(e.target.value)}
              className="flex-1 px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika"
              placeholder="Artist"
              disabled={isLoading}
            />
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="flex-1 px-2 py-1 text-sm border border-brick rounded focus:outline-none focus:ring-2 focus:ring-paprika"
              placeholder="Title"
              disabled={isLoading}
            />
          </div>

          {/* Save/Cancel Buttons */}
          <div className="flex-shrink-0 flex gap-2">
            <button
              onClick={handleSaveEdit}
              disabled={isLoading}
              className="px-3 py-1 text-sm font-medium text-white bg-paprika rounded hover:bg-saffron disabled:bg-paprika/50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={handleCancelEdit}
              disabled={isLoading}
              className="px-3 py-1 text-sm font-medium text-carbon bg-brick-light rounded hover:bg-brick disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Display Mode */}
          {/* Timestamp */}
          <button
            onClick={() => onClick?.(track)}
            className="flex-shrink-0 w-20 text-sm font-mono text-carbon/60 hover:text-paprika hover:underline cursor-pointer text-left transition-colors"
            title="Seek to this track in the video"
          >
            {formatTimestamp(track.start_time_ms)}
          </button>

          {/* Track Info */}
          <div className={`flex-grow min-w-0 text-sm ${isUnidentified ? 'text-carbon/60 italic' : 'text-carbon'}`}>
            <span className="truncate">{displayText}</span>
          </div>

          {/* Confidence Badge */}
          {track.confidence_score !== null && (
            <div
              className={`flex-shrink-0 px-2 py-1 rounded text-xs font-medium ${getConfidenceBadgeClasses(track.confidence_score)}`}
            >
              {Math.round(track.confidence_score * 100)}%
            </div>
          )}

          {/* Transition Indicator */}
          {track.is_transition && (
            <div className="flex-shrink-0 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
              Transition
            </div>
          )}

          {/* Edit/Delete Buttons */}
          <div className="flex-shrink-0 flex gap-2">
            <button
              onClick={handleEditClick}
              className="px-3 py-1 text-sm font-medium text-paprika bg-sand-light rounded hover:bg-sand transition-colors"
            >
              Edit
            </button>
            
            {isDeleting ? (
              <>
                <button
                  onClick={handleConfirmDelete}
                  disabled={isLoading}
                  className="px-3 py-1 text-sm font-medium text-white bg-danger rounded hover:bg-danger/80 disabled:bg-danger/40 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? 'Deleting...' : 'Confirm'}
                </button>
                <button
                  onClick={handleCancelDelete}
                  disabled={isLoading}
                  className="px-3 py-1 text-sm font-medium text-carbon bg-brick-light rounded hover:bg-brick disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                onClick={handleDeleteClick}
                className="px-3 py-1 text-sm font-medium text-danger bg-danger-light rounded hover:bg-danger/10 transition-colors"
              >
                Delete
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
