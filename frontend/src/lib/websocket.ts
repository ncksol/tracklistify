'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Progress state returned by the useJobProgress hook
 */
export interface JobProgressState {
  status: string | null;
  progress: number;
  error: string | null;
  connected: boolean;
}

/**
 * Message structure received from WebSocket
 */
interface WebSocketMessage {
  status?: string;
  progress?: number;
  error?: string;
}

const MAX_RETRIES = 5;
const INITIAL_RETRY_DELAY = 1000; // 1 second

/**
 * Custom React hook for tracking job progress via WebSocket
 *
 * @param jobId - The job ID to track, or null to not connect
 * @returns Current job progress state
 *
 * @example
 * ```tsx
 * const { status, progress, error, connected } = useJobProgress(jobId);
 * ```
 */
export function useJobProgress(jobId: string | null): JobProgressState {
  const [state, setState] = useState<JobProgressState>({
    status: null,
    progress: 0,
    error: null,
    connected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectingRef = useRef(false);

  useEffect(() => {
    // Don't connect if jobId is null
    if (!jobId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({
        status: null,
        progress: 0,
        error: null,
        connected: false,
      });
      return;
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL;
    if (!wsUrl) {
      setState((prev) => ({
        ...prev,
        error: 'WebSocket URL not configured',
        connected: false,
      }));
      return;
    }

    const connectWebSocket = () => {
      // Clean up existing connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const url = `${wsUrl}/ws/jobs/${jobId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({
          ...prev,
          connected: true,
          error: null,
        }));
        retryCountRef.current = 0;
        reconnectingRef.current = false;
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          setState((prev) => ({
            status: data.status ?? prev.status,
            progress: data.progress ?? prev.progress,
            error: data.error ?? prev.error,
            connected: true,
          }));
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setState((prev) => ({
          ...prev,
          error: 'WebSocket connection error',
        }));
      };

      ws.onclose = () => {
        setState((prev) => ({
          ...prev,
          connected: false,
        }));

        // Attempt to reconnect with exponential backoff
        if (retryCountRef.current < MAX_RETRIES && !reconnectingRef.current) {
          reconnectingRef.current = true;
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCountRef.current);

          retryTimeoutRef.current = setTimeout(() => {
            retryCountRef.current++;
            connectWebSocket();
          }, delay);
        } else if (retryCountRef.current >= MAX_RETRIES) {
          setState((prev) => ({
            ...prev,
            error: 'Max reconnection attempts reached',
          }));
        }
      };
    };

    connectWebSocket();

    // Cleanup function
    return () => {
      reconnectingRef.current = false;

      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [jobId]);

  return state;
}
