import React from 'react';
import type { AudioBitrate } from '../types';
import { Zap } from 'lucide-react';

interface SettingsBarProps {
  bitrate: AudioBitrate;
  onBitrateChange: (bitrate: AudioBitrate) => void;
  skipExisting: boolean;
  onSkipExistingChange: (skip: boolean) => void;
}

export const SettingsBar: React.FC<SettingsBarProps> = ({
  bitrate,
  onBitrateChange,
  skipExisting,
  onSkipExistingChange,
}) => {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-6 pt-5 border-t border-slate-100">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-slate-500">Quality:</span>
        <div className="flex items-center p-1 bg-[#f1f4f9] rounded-full border border-slate-200/60">
          <button
            type="button"
            onClick={() => onBitrateChange('320k')}
            title="Studio 320 kbps (Best Quality, ~9MB/track)"
            className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
              bitrate === '320k'
                ? 'bg-white text-blue-600 shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            320k (HQ)
          </button>
          <button
            type="button"
            onClick={() => onBitrateChange('192k')}
            title="Balanced 192 kbps (Standard, ~5MB/track)"
            className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
              bitrate === '192k'
                ? 'bg-white text-blue-600 shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            192k (Balanced)
          </button>
          <button
            type="button"
            onClick={() => onBitrateChange('128k')}
            title="Compressed 128 kbps (Storage Saver, ~3MB/track, Saves 60% space)"
            className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
              bitrate === '128k'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            🗜️ 128k (Compressed)
          </button>
        </div>
      </div>

      {/* Skip Existing Toggle */}
      <label
        className="flex items-center gap-2 cursor-pointer select-none text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
        title="Reuses existing downloaded tracks across playlists to save time and bandwidth"
      >
        <div className="relative inline-block w-9 h-5">
          <input
            type="checkbox"
            checked={skipExisting}
            onChange={(e) => onSkipExistingChange(e.target.checked)}
            className="opacity-0 w-0 h-0 peer"
          />
          <span className="absolute cursor-pointer inset-0 bg-slate-200 peer-checked:bg-blue-600 rounded-full transition-colors duration-300 before:absolute before:content-[''] before:h-3.5 before:w-3.5 before:left-0.5 before:bottom-0.5 before:bg-white before:rounded-full before:transition-transform before:duration-300 peer-checked:before:translate-x-4 shadow-2xs" />
        </div>
        <span className="flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
          Skip duplicates
        </span>
      </label>
    </div>
  );
};
