'use client';

import { useEffect, useRef } from 'react';

interface JobEvent {
  id: string;
  timestamp: string;  // ISO 8601
  message: string;
  phase: string;
  progress: number;
}

interface ActivityLogProps {
  events: JobEvent[];
  startTime: string;  // ISO timestamp of when job started, for relative time calc
}

/**
 * Format elapsed time from start to event timestamp
 * Returns formats like: "0s", "8s", "1m 30s", "5m 12s"
 */
function formatElapsedTime(startTime: string, eventTime: string): string {
  const start = new Date(startTime).getTime();
  const event = new Date(eventTime).getTime();
  const elapsedMs = event - start;
  const elapsedSec = Math.floor(elapsedMs / 1000);

  if (elapsedSec < 60) {
    return `${elapsedSec}s`;
  }

  const minutes = Math.floor(elapsedSec / 60);
  const seconds = elapsedSec % 60;
  return `${minutes}m ${seconds}s`;
}

export function ActivityLog({ events, startTime }: ActivityLogProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when events change
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div>
      {/* Header */}
      <div className="text-sm font-medium text-gray-500 mb-2">
        Activity Log
      </div>

      {/* Scrollable event container */}
      <div
        ref={containerRef}
        className="max-h-[300px] overflow-y-auto bg-carbon rounded-lg border border-carbon p-4"
      >
        {events.length === 0 ? (
          <div className="text-sm italic text-gray-400">
            Waiting for events...
          </div>
        ) : (
          events.map((event, index) => {
            const previousEvent = index > 0 ? events[index - 1] : null;
            const isNewPhase = previousEvent && previousEvent.phase !== event.phase;

            return (
              <div key={event.id}>
                {/* Phase separator */}
                {isNewPhase && (
                  <div className="border-t border-carbon my-2" />
                )}
                
                {/* Event entry */}
                <div className="text-sm font-mono text-saffron">
                  <span className="text-saffron inline-block w-16 text-right mr-3">
                    {formatElapsedTime(startTime, event.timestamp)}
                  </span>
                  <span>{event.message}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
