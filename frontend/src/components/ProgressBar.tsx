'use client';

interface ProgressBarProps {
  status: string | null;
  progress: number;
  error: string | null;
}

const STATUS_LABELS: Record<string, string> = {
  QUEUED: 'Waiting in queue...',
  DOWNLOADING: 'Downloading audio...',
  SEGMENTING: 'Segmenting audio...',
  FINGERPRINTING: 'Identifying tracks...',
  AGGREGATING: 'Building tracklist...',
  COMPLETE: 'Complete!',
  FAILED: 'Failed',
};

export function ProgressBar({ status, progress, error }: ProgressBarProps) {

  const statusLabel = status ? STATUS_LABELS[status] || status : 'Initializing...';
  
  // Determine progress bar color based on status
  const getProgressColor = () => {
    if (status === 'COMPLETE') return 'bg-green-500';
    if (status === 'FAILED' || error) return 'bg-danger';
    return 'bg-paprika';
  };

  return (
    <div className="w-full space-y-2">
      {/* Status label */}
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-gray-700">
          {statusLabel}
        </span>
        <span className="text-sm text-gray-500">
          {progress}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-brick rounded-full overflow-hidden">
        <div
          className={`h-full ${getProgressColor()} transition-all duration-300 ease-out`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Error message */}
      {error && (
        <div className="text-sm text-danger">
          {error}
        </div>
      )}
    </div>
  );
}
