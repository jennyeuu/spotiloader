import React from 'react';
import type { JobStatusResponse, TrackDetail } from '../types';
import { Download, CheckCircle2, AlertCircle, Clock, Zap, Archive, Music, X } from 'lucide-react';

interface ProgressMonitorProps {
  job: JobStatusResponse | null;
  playlistTitle: string;
  onDismiss?: () => void;
}

export const ProgressMonitor: React.FC<ProgressMonitorProps> = ({ job, playlistTitle, onDismiss }) => {
  if (!job) return null;

  const getStatusBadge = (status: JobStatusResponse['status']) => {
    switch (status) {
      case 'PROGRESS':
        return <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-600 border border-blue-200">Processing</span>;
      case 'SUCCESS':
        return <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-200">Completed</span>;
      case 'PARTIAL_SUCCESS':
        return <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-600 border border-amber-200">Partial</span>;
      case 'FAILURE':
        return <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-rose-50 text-rose-600 border border-rose-200">Failed</span>;
      default:
        return <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-slate-100 text-slate-600">Queued</span>;
    }
  };

  const getScoreBadge = (track: TrackDetail) => {
    if (track.cached) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-600 border border-blue-200/80">
          <Zap className="w-3 h-3 text-blue-600 fill-blue-600" />
          Cached
        </span>
      );
    }
    if (track.match_score !== null && track.match_score !== undefined) {
      const s = Math.round(track.match_score);
      const colorClass = s >= 80 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : s >= 60 ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-rose-50 text-rose-700 border-rose-200';
      return <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${colorClass}`}>{s}% Match</span>;
    }
    return <span className="text-slate-400 text-xs">-</span>;
  };

  const getTrackStatusBadge = (track: TrackDetail) => {
    if (track.status === 'completed') {
      return (
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
          <CheckCircle2 className="w-4 h-4" />
          {track.cached ? 'Reused' : 'Done'}
        </span>
      );
    }
    if (track.status === 'failed') {
      return (
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-500" title={track.error || 'Failed'}>
          <AlertCircle className="w-4 h-4" />
          Failed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600">
        <Clock className="w-4 h-4 animate-spin" />
        Matching
      </span>
    );
  };

  return (
    <section className="mt-6 space-y-4 animate-fade-in">
      <div className="neumorphic-card rounded-3xl p-6 border border-slate-100">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 shadow-2xs border border-blue-100/50">
              <Music className="w-6 h-6 stroke-[2.2]" />
            </div>

            <div>
              <h2 className="text-base font-bold text-slate-800 tracking-tight">{playlistTitle || 'Downloading Playlist'}</h2>
              <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5 font-medium">
                <span>MP3 • {job.bitrate || '320k'}</span>
                <span>•</span>
                <span>{job.completed_tracks}/{job.total_tracks} tracks</span>
                <span>•</span>
                <span>{job.progress_percentage.toFixed(0)}% done</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {getStatusBadge(job.status)}
            {onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition-colors"
                title="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-2">
          <div
            className="h-full bg-[#0066ff] rounded-full transition-all duration-500"
            style={{ width: `${job.progress_percentage}%` }}
          />
        </div>

        {job.current_track && job.status === 'PROGRESS' && (
          <div className="flex items-center gap-2.5 pt-2 text-xs font-semibold text-blue-600 truncate">
            <div className="flex items-end gap-0.5 h-3">
              <span className="w-0.5 bg-blue-600 rounded-full animate-eq-1" />
              <span className="w-0.5 bg-blue-600 rounded-full animate-eq-2" />
              <span className="w-0.5 bg-blue-600 rounded-full animate-eq-3" />
              <span className="w-0.5 bg-blue-600 rounded-full animate-eq-4" />
            </div>
            <span className="truncate">{job.current_track}</span>
          </div>
        )}

        {job.completed_tracks > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100 flex justify-end">
            <a
              href={`/api/playlist/download-zip/${job.job_id}`}
              download
              className="inline-flex items-center gap-2 bg-[#0066ff] hover:bg-blue-600 text-white px-5 py-2.5 rounded-full text-xs font-bold transition-all shadow-md shadow-blue-500/20"
            >
              <Archive className="w-4 h-4" />
              Download All as ZIP (.zip)
            </a>
          </div>
        )}
      </div>

      <div className="neumorphic-card rounded-3xl p-6 border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-slate-800 text-sm">Tracklist Details</h3>
          <span className="text-xs text-slate-400 font-medium">{job.completed_tracks} of {job.total_tracks} processed</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="text-slate-400 border-b border-slate-100 font-bold uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3 w-8 text-center">#</th>
                <th className="py-2.5 px-3">Title & Artist</th>
                <th className="py-2.5 px-3">Matched YouTube Source</th>
                <th className="py-2.5 px-2">Match</th>
                <th className="py-2.5 px-2">Status</th>
                <th className="py-2.5 px-3 text-right">MP3</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
              {job.tracks_detail.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    Matching tracks with YouTube Music audio engine...
                  </td>
                </tr>
              ) : (
                job.tracks_detail.map((track, idx) => (
                  <tr key={track.track_id || idx} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-3 text-center text-slate-400 font-mono text-[11px]">{idx + 1}</td>
                    <td className="py-3 px-3">
                      <div className="font-bold text-slate-800">{track.title}</div>
                      <div className="text-[11px] text-slate-400">{track.artist}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-500 max-w-[200px] truncate text-[11px]">
                      {track.matched_title || '-'}
                    </td>
                    <td className="py-3 px-2">{getScoreBadge(track)}</td>
                    <td className="py-3 px-2">{getTrackStatusBadge(track)}</td>
                    <td className="py-3 px-3 text-right">
                      {track.status === 'completed' && track.file_path ? (
                        <a
                          href={`/api/playlist/download-track?file_path=${encodeURIComponent(track.file_path)}`}
                          download
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-blue-600 hover:text-white hover:bg-blue-600 bg-blue-50 px-2.5 py-1 rounded-full transition-all"
                          title="Download MP3"
                        >
                          <Download className="w-3 h-3" />
                          Save
                        </a>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
