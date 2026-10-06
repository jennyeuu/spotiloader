import React, { useState, useRef } from 'react';
import { Upload, FileText, Loader2 } from 'lucide-react';

interface CsvDropzoneProps {
  onSubmit: (file: File, playlistName: string) => Promise<void>;
  isLoading: boolean;
  onCancel?: () => void;
}

export const CsvDropzone: React.FC<CsvDropzoneProps> = ({ onSubmit, isLoading, onCancel }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [playlistName, setPlaylistName] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const processFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      alert('Please upload a valid .csv file');
      return;
    }
    setSelectedFile(file);
    if (!playlistName) {
      setPlaylistName(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    onSubmit(selectedFile, playlistName.trim() || 'Imported CSV Playlist');
  };

  const handleClear = () => {
    setSelectedFile(null);
    setPlaylistName('');
    if (onCancel) onCancel();
  };

  return (
    <div>
      {/* Upload Box (Matches the exact rounded dashed container and 3D blue sphere) */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-3xl p-8 sm:p-10 text-center cursor-pointer transition-all bg-[#fafbfc] ${
          isDragOver
            ? 'border-blue-500 bg-blue-50/50'
            : 'border-slate-200/90 hover:border-blue-300'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => e.target.files?.length && processFile(e.target.files[0])}
          accept=".csv"
          className="hidden"
        />

        <div className="font-bold text-slate-800 text-lg mb-6 tracking-tight">
          Drop your playlist CSV here
        </div>

        {/* 3D Floating Blue Sphere */}
        <div className="w-20 h-20 rounded-full sphere-glow text-blue-600 flex items-center justify-center mx-auto mb-6 animate-sphere transition-transform">
          <Upload className="w-8 h-8 stroke-[2.5]" />
        </div>

        <div className="text-slate-400 text-xs sm:text-sm max-w-sm mx-auto leading-relaxed">
          For best results, upload CSV exports from <strong className="text-slate-600">TuneMyMusic</strong>, <strong className="text-slate-600">Exportify</strong>, or <strong className="text-slate-600">CSVMusic</strong>.
        </div>

        {selectedFile && (
          <div className="inline-flex items-center gap-2 mt-5 px-4 py-2 rounded-2xl bg-white border border-slate-200 text-slate-700 text-xs font-semibold shadow-xs">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>{selectedFile.name}</span>
            <span className="text-slate-400">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
          </div>
        )}
      </div>

      {/* Input Name & Action Buttons */}
      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        {selectedFile && (
          <input
            type="text"
            value={playlistName}
            onChange={(e) => setPlaylistName(e.target.value)}
            placeholder="Custom Playlist Title"
            className="w-full bg-[#f8fafc] border border-slate-200 rounded-2xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-blue-500 focus:bg-white transition-all"
          />
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={handleClear}
            className="w-full bg-[#f1f4f9] hover:bg-slate-200/80 text-slate-700 font-bold py-3.5 px-6 rounded-full text-sm transition-all text-center"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={isLoading || !selectedFile}
            className="w-full bg-[#0066ff] hover:bg-blue-600 disabled:opacity-50 text-white font-bold py-3.5 px-6 rounded-full text-sm transition-all shadow-md shadow-blue-500/25 flex items-center justify-center gap-2 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Processing...</span>
              </>
            ) : (
              <span>Upload</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
