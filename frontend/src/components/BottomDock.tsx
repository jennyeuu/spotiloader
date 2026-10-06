import React from 'react';
import { Home, FolderClosed, Plus, Bell, User } from 'lucide-react';

interface BottomDockProps {
  activeTab: 'url' | 'csv';
  onTabChange: (tab: 'url' | 'csv') => void;
  onActionClick: () => void;
}

export const BottomDock: React.FC<BottomDockProps> = ({ activeTab, onTabChange, onActionClick }) => {
  return (
    <nav className="flex items-center justify-between px-6 py-2.5 bg-white/90 backdrop-blur-md rounded-full shadow-lg shadow-slate-900/5 border border-slate-100 max-w-sm mx-auto mt-8">
      {/* Home (URL) */}
      <button
        type="button"
        onClick={() => onTabChange('url')}
        className={`flex flex-col items-center gap-1 transition-all ${
          activeTab === 'url' ? 'text-blue-600' : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        <Home className="w-5 h-5 stroke-[2]" />
        <span className="text-[10px] font-bold">URL</span>
      </button>

      {/* Files (CSV) */}
      <button
        type="button"
        onClick={() => onTabChange('csv')}
        className={`flex flex-col items-center gap-1 transition-all ${
          activeTab === 'csv' ? 'text-blue-600' : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        <FolderClosed className="w-5 h-5 stroke-[2]" />
        <span className="text-[10px] font-bold">CSV</span>
      </button>

      {/* Center Floating Plus Button */}
      <div className="-mt-8">
        <button
          type="button"
          onClick={onActionClick}
          title="New Download"
          className="w-14 h-14 rounded-full bg-white text-slate-800 flex items-center justify-center floating-button-shadow border border-slate-100 hover:scale-105 active:scale-95 transition-all"
        >
          <Plus className="w-6 h-6 stroke-[2.5]" />
        </button>
      </div>

      {/* Status / Alerts */}
      <button
        type="button"
        onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}
        className="flex flex-col items-center gap-1 text-slate-400 hover:text-slate-600 transition-all"
      >
        <Bell className="w-5 h-5 stroke-[2]" />
        <span className="text-[10px] font-bold">Status</span>
      </button>

      {/* Info / GitHub */}
      <a
        href="https://github.com/angall1/CSVMusic"
        target="_blank"
        rel="noreferrer"
        className="flex flex-col items-center gap-1 text-slate-400 hover:text-slate-600 transition-all"
      >
        <User className="w-5 h-5 stroke-[2]" />
        <span className="text-[10px] font-bold">About</span>
      </a>
    </nav>
  );
};
