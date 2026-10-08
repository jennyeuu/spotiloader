export type AudioBitrate = '320k' | '192k' | '128k';

export interface TrackDetail {
  track_id?: string;
  title: string;
  artist: string;
  status: 'ready' | 'in_progress' | 'completed' | 'failed';
  matched_title?: string | null;
  match_score?: number | null;
  file_path?: string | null;
  cached?: boolean;
  error?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'READY' | 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILURE';
  total_tracks: number;
  completed_tracks: number;
  failed_tracks: number;
  progress_percentage: number;
  bitrate?: string;
  current_track?: string | null;
  tracks_detail: TrackDetail[];
  error?: string | null;
}

export interface PlaylistSubmitResponse {
  job_id: string;
  playlist_title: string;
  total_tracks: number;
  source: string;
  skip_existing: boolean;
  bitrate: string;
  message: string;
}
