/**
 * API client for Tracklistify backend
 */

// Read API URL from environment variable, default to localhost
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// Type Definitions (matching Pydantic models)
// ============================================================================

export interface Job {
  id: string;
  youtube_url: string;
  video_title: string | null;
  duration_seconds: number | null;
  confidence_threshold: number;
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Track {
  id: string;
  job_id?: string;
  position: number;
  start_time_ms: number;
  end_time_ms: number | null;
  title: string | null;
  artist: string | null;
  album: string | null;
  confidence_score: number | null;
  is_transition: boolean;
  is_manual_edit: boolean;
}

export interface UnidentifiedSegment {
  id: string;
  job_id?: string;
  start_time_ms: number;
  end_time_ms: number;
  notes: string | null;
}

export interface Tracklist {
  job_id: string;
  tracks: Track[];
  unidentified_segments: UnidentifiedSegment[];
}

export interface WaveformData {
  peaks: number[];
  duration_seconds: number;
  sample_rate: number;
}

export interface TrackCreateData {
  position: number;
  start_time_ms: number;
  end_time_ms: number;
  title: string;
  artist: string;
}

export interface ShareResponse {
  slug: string;
  url: string;
}

export interface JobEvent {
  id: string;
  job_id: string;
  timestamp: string;
  message: string;
  phase: string;
  progress: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Handle API response errors
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage: string;

    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.detail || errorJson.message || errorText;
    } catch {
      errorMessage = errorText || response.statusText;
    }

    throw new Error(`API Error (${response.status}): ${errorMessage}`);
  }

  return response.json();
}

/**
 * Build full API URL
 */
function buildUrl(path: string): string {
  return `${API_URL}${path}`;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a new job for processing a YouTube URL
 */
export async function createJob(
  url: string,
  force = false,
  confidence_threshold = 0.5,
): Promise<Job> {
  const response = await fetch(buildUrl('/api/jobs'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url, force, confidence_threshold }),
  });

  return handleResponse<Job>(response);
}

/**
 * Get job status and details
 */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}`));
  return handleResponse<Job>(response);
}

/**
 * Get job events for real-time progress updates
 */
export async function getJobEvents(jobId: string, after?: string): Promise<JobEvent[]> {
  const params = after ? `?after=${encodeURIComponent(after)}` : '';
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/events${params}`));
  const data = await handleResponse<{ events: JobEvent[] }>(response);
  return data.events;
}

/**
 * Get the ordered tracklist for a completed job
 */
export async function getTracklist(jobId: string): Promise<Tracklist> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/tracklist`));
  return handleResponse<Tracklist>(response);
}

/**
 * Get waveform data for audio visualization
 */
export async function getWaveform(jobId: string): Promise<WaveformData> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/waveform`));
  return handleResponse<WaveformData>(response);
}

/**
 * Update track fields (sets is_manual_edit = true)
 */
export async function updateTrack(
  jobId: string,
  trackId: string,
  data: Partial<Pick<Track, 'artist' | 'title' | 'start_time_ms' | 'end_time_ms'>>,
): Promise<Track> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/tracks/${trackId}`), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  return handleResponse<Track>(response);
}

/**
 * Delete a track (false positive removal)
 */
export async function deleteTrack(jobId: string, trackId: string): Promise<void> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/tracks/${trackId}`), {
    method: 'DELETE',
  });

  if (!response.ok) {
    await handleResponse(response);
  }
}

export async function deleteUnidentifiedSegment(jobId: string, segmentId: string): Promise<void> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/unidentified/${segmentId}`), {
    method: 'DELETE',
  });

  if (!response.ok) {
    await handleResponse(response);
  }
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}`), {
    method: 'DELETE',
  });

  if (!response.ok) {
    await handleResponse(response);
  }
}

/**
 * Manually add a track (fill unidentified gap)
 */
export async function createTrack(jobId: string, data: TrackCreateData): Promise<Track> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/tracks`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  return handleResponse<Track>(response);
}

/**
 * Get list of jobs (paginated)
 * Note: This endpoint may need to be implemented in the backend
 */
export async function getJobs(page: number = 1): Promise<Job[]> {
  const response = await fetch(buildUrl(`/api/jobs?page=${page}`));
  const data = await handleResponse<{ jobs: Job[]; total: number; page: number; per_page: number }>(
    response,
  );
  return data.jobs;
}

/**
 * Share a job and get a shareable URL
 * Note: This endpoint may need to be implemented in the backend
 */
export async function shareJob(jobId: string): Promise<ShareResponse> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/share`), {
    method: 'POST',
  });

  return handleResponse<ShareResponse>(response);
}

/**
 * Get shared tracklist by slug
 * Note: This endpoint may need to be implemented in the backend
 */
export async function getSharedTracklist(slug: string): Promise<Tracklist> {
  const response = await fetch(buildUrl(`/api/shared/${slug}`));
  return handleResponse<Tracklist>(response);
}
