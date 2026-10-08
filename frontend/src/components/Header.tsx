import React from 'react';
import { Music, Disc, Sparkles, RefreshCw } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="text-center mb-10">
      <div className="flex items-center justify-between max-w-2xl mx-auto mb-6 px-2">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-black text-base shadow-md shadow-blue-500/20">
            S
          </div>
          <span className="font-extrabold text-slate-800 text-xl tracking-tight">spotiloader</span>
        </div>
        <span className="text-xs font-semibold text-slate-400 bg-white/80 px-3 py-1 rounded-full border border-slate-200/60 shadow-2xs">
          DRM-Free Studio
        </span>
      </div>

      <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight mb-3">
        Metadata-Matched <span className="text-blue-600">Music Downloader</span>
      </h1>
      <p className="text-slate-500 text-sm sm:text-base max-w-xl mx-auto">
        Convert Spotify playlists & CSV exports into 320kbps MP3s with full ID3 tags and cover artwork.
      </p>

      <div className="flex flex-wrap justify-center gap-2.5 mt-6">
        <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white border border-slate-200/80 text-slate-600 text-xs font-semibold shadow-xs">
          <Music className="w-3.5 h-3.5 text-blue-600" />
          320k - 128k Bitrates
        </div>
        <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white border border-slate-200/80 text-slate-600 text-xs font-semibold shadow-xs">
          <Disc className="w-3.5 h-3.5 text-blue-500" />
          Embedded Cover Art
        </div>
        <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white border border-slate-200/80 text-slate-600 text-xs font-semibold shadow-xs">
          <Sparkles className="w-3.5 h-3.5 text-sky-500" />
          Smart YouTube Matching
        </div>
        <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white border border-slate-200/80 text-slate-600 text-xs font-semibold shadow-xs">
          <RefreshCw className="w-3.5 h-3.5 text-indigo-500" />
          Zero API Key Required
        </div>
      </div>
    </header>
  );
};
