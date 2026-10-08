import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { UrlInputForm } from './components/UrlInputForm';
import { CsvDropzone } from './components/CsvDropzone';
import { SettingsBar } from './components/SettingsBar';
import { ProgressMonitor } from './components/ProgressMonitor';
import { BottomDock } from './components/BottomDock';
import type { AudioBitrate, JobStatusResponse, PlaylistSubmitResponse } from './types';
import { Link2, FileSpreadsheet, CheckCircle2, AlertTriangle, Info, X } from 'lucide-react';

interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  text: string;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'url' | 'csv'>('url');
  const [bitrate, setBitrate] = useState<AudioBitrate>('320k');
  const [skipExisting, setSkipExisting] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [playlistTitle, setPlaylistTitle] = useState<string>('');
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const pollIntervalRef = useRef<number | null>(null);

  const addToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, text }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleBitrateChange = (newBitrate: AudioBitrate) => {
    setBitrate(newBitrate);
    if (newBitrate === '128k') {
      addToast('Storage Saver Mode: 128 kbps (~60% smaller file sizes)', 'info');
    }
  };

  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isDownloadingAll, setIsDownloadingAll] = useState<boolean>(false);

  const startPolling = (jobId?: string) => {
    const id = jobId || currentJobId;
    if (!id) return;
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    const poll = async () => {
      try {
        const res = await fetch(`/api/playlist/status/${id}`);
        if (!res.ok) return;
        const data: JobStatusResponse = await res.json();
        setJobStatus(data);

        if (data.status === 'SUCCESS' || data.status === 'FAILURE' || data.status === 'PARTIAL_SUCCESS') {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          if (data.status === 'SUCCESS') {
            addToast('All tracks downloaded, converted, and tagged!', 'success');
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    };

    poll();
    pollIntervalRef.current = window.setInterval(poll, 1500);
  };

  const handleUrlSubmit = async (url: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/playlist/submit-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          skip_existing: skipExisting,
          bitrate,
        }),
      });

      const data: PlaylistSubmitResponse = await res.json();
      if (!res.ok) {
        throw new Error((data as any).detail || 'Failed to extract Spotify playlist.');
      }

      setPlaylistTitle(data.playlist_title);
      setCurrentJobId(data.job_id);
      addToast(`Loaded "${data.playlist_title}" (${data.total_tracks} tracks). Ready for download!`, 'success');

      // fetch loaded status immediately and start polling
      const sRes = await fetch(`/api/playlist/status/${data.job_id}`);
      if (sRes.ok) {
        const sData = await sRes.json();
        setJobStatus(sData);
      }
      startPolling(data.job_id);
    } catch (err: any) {
      addToast(err.message || 'Error submitting Spotify URL', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCsvSubmit = async (file: File, name: string) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('playlist_name', name);
      formData.append('skip_existing', String(skipExisting));
      formData.append('bitrate', bitrate);

      const res = await fetch('/api/playlist/submit-csv', {
        method: 'POST',
        body: formData,
      });

      const data: PlaylistSubmitResponse = await res.json();
      if (!res.ok) {
        throw new Error((data as any).detail || 'Failed to process CSV file.');
      }

      setPlaylistTitle(data.playlist_title);
      setCurrentJobId(data.job_id);
      addToast(`Loaded "${data.playlist_title}" (${data.total_tracks} tracks). Ready for download!`, 'success');

      const sRes = await fetch(`/api/playlist/status/${data.job_id}`);
      if (sRes.ok) {
        const sData = await sRes.json();
        setJobStatus(sData);
      }
      startPolling(data.job_id);
    } catch (err: any) {
      addToast(err.message || 'Error processing CSV file', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadAll = async () => {
    if (!currentJobId) return;
    setIsDownloadingAll(true);
    addToast('Starting batch download for all remaining tracks...', 'info');
    try {
      const res = await fetch(`/api/playlist/download-all/${currentJobId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to start batch download.');
      }
      const updated: JobStatusResponse = await res.json();
      setJobStatus(updated);
      startPolling();
    } catch (err: any) {
      addToast(err.message || 'Error starting download all', 'error');
    } finally {
      setIsDownloadingAll(false);
    }
  };

  const handleDownloadSingleTrack = async (trackId?: string) => {
    if (!currentJobId) return;
    addToast('Downloading song into playlist folder...', 'info');
    try {
      const targetId = trackId || '0';
      const res = await fetch(`/api/playlist/download-track/${currentJobId}/${encodeURIComponent(targetId)}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to download track.');
      }
      const updated: JobStatusResponse = await res.json();
      setJobStatus(updated);
      startPolling();
    } catch (err: any) {
      addToast(err.message || 'Error downloading song', 'error');
    }
  };

  const handleRetryFailed = async () => {
    if (!currentJobId) return;
    setIsRetrying(true);
    addToast('Retrying failed tracks with alternative search sources...', 'info');
    try {
      const res = await fetch(`/api/playlist/retry-failed/${currentJobId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to trigger retry.');
      }
      const updated: JobStatusResponse = await res.json();
      setJobStatus(updated);
      startPolling();
    } catch (err: any) {
      addToast(err.message || 'Error triggering retry', 'error');
    } finally {
      setIsRetrying(false);
    }
  };

  // poll download job progress on mount/jobId change
  useEffect(() => {
    if (!currentJobId) return;
    startPolling(currentJobId);
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [currentJobId]);

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6">
      <div className="max-w-3xl sm:max-w-4xl mx-auto">
        <Header />

        <main className="neumorphic-card rounded-[36px] p-8 sm:p-12 border border-white">
          <div className="flex items-center gap-2 p-1.5 bg-[#f1f4f9] rounded-full border border-slate-200/60 mb-8 max-w-md mx-auto">
            <button
              type="button"
              onClick={() => setActiveTab('url')}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-xs sm:text-sm font-bold transition-all ${
                activeTab === 'url'
                  ? 'bg-white text-blue-600 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <Link2 className="w-4 h-4 stroke-[2.5]" />
              Spotify / YouTube Link
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('csv')}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-xs sm:text-sm font-bold transition-all ${
                activeTab === 'csv'
                  ? 'bg-white text-blue-600 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <FileSpreadsheet className="w-4 h-4 stroke-[2.5]" />
              CSV Export Import
            </button>
          </div>

          {activeTab === 'url' ? (
            <UrlInputForm onSubmit={handleUrlSubmit} isLoading={isLoading} />
          ) : (
            <CsvDropzone onSubmit={handleCsvSubmit} isLoading={isLoading} />
          )}

          <SettingsBar
            bitrate={bitrate}
            onBitrateChange={handleBitrateChange}
            skipExisting={skipExisting}
            onSkipExistingChange={setSkipExisting}
          />
        </main>

        <ProgressMonitor
          job={jobStatus}
          playlistTitle={playlistTitle}
          onDismiss={() => {
            setCurrentJobId(null);
            setJobStatus(null);
          }}
          onRetryFailed={handleRetryFailed}
          isRetrying={isRetrying}
          onDownloadAll={handleDownloadAll}
          isDownloadingAll={isDownloadingAll}
          onDownloadTrack={handleDownloadSingleTrack}
        />

        <BottomDock
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onActionClick={() => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
            setActiveTab((prev) => (prev === 'url' ? 'csv' : 'url'));
          }}
        />

        <div className="flex items-center justify-between text-xs font-semibold text-slate-400 mt-8 px-4">
          <span>spotiloader.app</span>
          <span>DRM-Free Music Downloader</span>
        </div>
      </div>

      {/* Toast Notification Container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center justify-between gap-3 px-4 py-3 rounded-2xl border shadow-lg text-xs font-bold transition-all animate-fade-in ${
              t.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : t.type === 'error'
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : 'bg-white border-slate-200 text-slate-800'
            }`}
          >
            <div className="flex items-center gap-2">
              {t.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />}
              {t.type === 'error' && <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />}
              {t.type === 'info' && <Info className="w-4 h-4 text-blue-600 shrink-0" />}
              <span>{t.text}</span>
            </div>
            <button
              onClick={() => removeToast(t.id)}
              className="text-slate-400 hover:text-slate-700 p-0.5 rounded transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
