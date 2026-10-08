import React, { useState } from 'react';
import { Link2, Sparkles, Loader2 } from 'lucide-react';

interface UrlInputFormProps {
  onSubmit: (url: string) => Promise<void>;
  isLoading: boolean;
  onCancel?: () => void;
}

const SAMPLE_PLAYLISTS = [
  { name: 'Blinding Lights (Spotify)', url: 'https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b' },
  { name: "Today's Top Hits (Spotify)", url: 'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M' },
  { name: 'Chill Hits (Spotify)', url: 'https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6' },
  { name: 'Never Gonna Give You Up (YouTube)', url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
];

export const UrlInputForm: React.FC<UrlInputFormProps> = ({ onSubmit, isLoading, onCancel }) => {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim());
  };

  const handleClear = () => {
    setUrl('');
    if (onCancel) onCancel();
  };

  return (
    <div>
      <div className="border-2 border-dashed border-slate-200/90 rounded-3xl p-8 sm:p-10 text-center bg-[#fafbfc] transition-all">
        <div className="font-bold text-slate-800 text-lg mb-6 tracking-tight">
          Paste Spotify or YouTube URL here
        </div>

        <div className="w-20 h-20 rounded-full sphere-glow text-blue-600 flex items-center justify-center mx-auto mb-6 animate-sphere">
          <Link2 className="w-8 h-8 stroke-[2.5]" />
        </div>

        <div className="text-slate-400 text-xs sm:text-sm max-w-sm mx-auto leading-relaxed mb-6">
          Paste any public <strong className="text-slate-600">Spotify</strong> or <strong className="text-slate-600">YouTube</strong> Playlist, Album, Video, or Track link.
        </div>

        <div className="relative max-w-md mx-auto">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://open.spotify.com/... or https://youtube.com/playlist?list=..."
            className="w-full bg-white border border-slate-200 rounded-2xl px-4 py-3.5 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 shadow-xs transition-all"
            required
          />
        </div>
      </div>

      <div className="flex items-center justify-center flex-wrap gap-2 mt-4 text-xs text-slate-400">
        <span className="flex items-center gap-1 font-semibold text-slate-500">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          Popular samples:
        </span>
        {SAMPLE_PLAYLISTS.map((sample) => (
          <button
            key={sample.name}
            type="button"
            onClick={() => setUrl(sample.url)}
            className="px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-300 transition-all font-medium shadow-2xs"
          >
            {sample.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 mt-6">
        <button
          type="button"
          onClick={handleClear}
          className="w-full bg-[#f1f4f9] hover:bg-slate-200/80 text-slate-700 font-bold py-3.5 px-6 rounded-full text-sm transition-all text-center"
        >
          Cancel
        </button>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !url.trim()}
          className="w-full bg-[#0066ff] hover:bg-blue-600 disabled:opacity-50 text-white font-bold py-3.5 px-6 rounded-full text-sm transition-all shadow-md shadow-blue-500/25 flex items-center justify-center gap-2 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Extracting...</span>
            </>
          ) : (
            <span>Download</span>
          )}
        </button>
      </div>
    </div>
  );
};
