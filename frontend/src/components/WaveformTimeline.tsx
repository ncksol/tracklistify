'use client';

import { useEffect, useRef } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import type { Track, UnidentifiedSegment, WaveformData } from '@/lib/api';

interface WaveformTimelineProps {
  waveformData: WaveformData;
  tracks: Track[];
  unidentifiedSegments: UnidentifiedSegment[];
  onTrackClick?: (track: Track) => void;
}

// Generate distinct colors for tracks
const TRACK_COLORS = [
  'rgba(59, 130, 246, 0.5)',  // blue
  'rgba(16, 185, 129, 0.5)',  // green
  'rgba(245, 158, 11, 0.5)',  // amber
  'rgba(239, 68, 68, 0.5)',   // red
  'rgba(168, 85, 247, 0.5)',  // purple
  'rgba(236, 72, 153, 0.5)',  // pink
  'rgba(14, 165, 233, 0.5)',  // sky
  'rgba(34, 197, 94, 0.5)',   // emerald
];

const UNIDENTIFIED_COLOR = 'rgba(156, 163, 175, 0.3)'; // grey

export default function WaveformTimeline({
  waveformData,
  tracks,
  unidentifiedSegments,
  onTrackClick,
}: WaveformTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsPluginRef = useRef<RegionsPlugin | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize WaveSurfer with peaks data
    const wavesurfer = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#4f46e5',
      progressColor: '#818cf8',
      height: 128,
      normalize: true,
      interact: false, // Disable playback interaction since we only visualize
    });

    // Initialize Regions plugin
    const regions = wavesurfer.registerPlugin(RegionsPlugin.create());

    wavesurferRef.current = wavesurfer;
    regionsPluginRef.current = regions;

    // Load peaks data
    wavesurfer.load('', [waveformData.peaks], waveformData.duration_seconds);

    // Wait for waveform to be ready before adding regions
    wavesurfer.on('ready', () => {
      // Add regions for unidentified segments
      unidentifiedSegments.forEach((segment) => {
        const startTime = segment.start_time_ms / 1000;
        const endTime = segment.end_time_ms / 1000;

        const region = regions.addRegion({
          start: startTime,
          end: endTime,
          color: UNIDENTIFIED_COLOR,
          drag: false,
          resize: false,
          content: createUnidentifiedLabel(),
        });

        // Apply hatched pattern styling to the region element
        region.on('update-end', () => {
          applyHatchedPattern(region.element);
        });
        
        // Apply pattern immediately after creation
        setTimeout(() => {
          applyHatchedPattern(region.element);
        }, 0);
      });

      // Add regions for identified tracks
      tracks.forEach((track, index) => {
        const startTime = track.start_time_ms / 1000;
        const endTime = track.end_time_ms ? track.end_time_ms / 1000 : waveformData.duration_seconds;
        const color = TRACK_COLORS[index % TRACK_COLORS.length];

        const region = regions.addRegion({
          start: startTime,
          end: endTime,
          color: color,
          drag: false,
          resize: false,
          content: createTrackLabel(track),
        });

        // Handle region click
        region.on('click', () => {
          if (onTrackClick) {
            onTrackClick(track);
          }
        });
      });
    });

    // Cleanup on unmount
    return () => {
      wavesurfer.destroy();
    };
  }, [waveformData, tracks, unidentifiedSegments, onTrackClick]);

  return (
    <div className="w-full">
      <div ref={containerRef} className="w-full" />
    </div>
  );
}

/**
 * Create a label element for a track region
 */
function createTrackLabel(track: Track): HTMLElement {
  const label = document.createElement('div');
  label.style.cssText = `
    position: absolute;
    top: 4px;
    left: 4px;
    font-size: 11px;
    font-weight: 600;
    color: #1f2937;
    pointer-events: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: calc(100% - 8px);
  `;
  
  const trackName = track.artist && track.title 
    ? `${track.artist} - ${track.title}`
    : track.title || track.artist || `Track ${track.position}`;
  
  label.textContent = trackName;
  
  return label;
}

/**
 * Create a label element for an unidentified segment
 */
function createUnidentifiedLabel(): HTMLElement {
  const label = document.createElement('div');
  label.style.cssText = `
    position: absolute;
    top: 4px;
    left: 4px;
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
    pointer-events: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: calc(100% - 8px);
  `;
  
  label.textContent = 'Unidentified';
  
  return label;
}

/**
 * Apply a hatched/striped pattern to an unidentified region element
 */
function applyHatchedPattern(element: HTMLElement | null): void {
  if (!element) return;
  
  // Create a striped pattern using CSS linear gradient
  element.style.backgroundImage = `
    repeating-linear-gradient(
      45deg,
      rgba(156, 163, 175, 0.3),
      rgba(156, 163, 175, 0.3) 10px,
      rgba(156, 163, 175, 0.15) 10px,
      rgba(156, 163, 175, 0.15) 20px
    )
  `;
}
