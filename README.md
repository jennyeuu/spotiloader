# 🎵 Spotiloader

A clean, metadata-matched music downloader built to export Spotify playlists and CSV files into offline, DRM-free MP3s with complete ID3 tags and album cover artwork.

I developed **Spotiloader** because my parents are heading out on a trip and wanted their favorite music readily available offline without needing active mobile data, premium subscriptions, or complicated music managers.

I wanted something simple and reliable: paste a playlist link (or drop a CSV file), choose audio quality, and let it download everything into organized folders that can be easily dropped onto a phone, USB flash drive, or MP3 player.

---

## Features

- **Spotify URL & URI Parsing**: Paste public Spotify playlist, album, or track links directly (no developer credentials or API keys needed).
- **CSV Playlist Import**: Drag-and-drop CSV export files from services like **TuneMyMusic**, **Exportify**, **Soundiiz**, and **CSVMusic**.
- **Smart YouTube Matching**: Advanced fuzzy candidate scoring that matches Spotify metadata to official YouTube Music tracks while filtering out music video skits, unwanted live recordings, and mismatched durations.
- **Full ID3 Tagging & Cover Art**: Automatically injects track title, artists, album name, release year, track number, ISRC codes, and high-resolution cover art into every MP3.
- **Audio Bitrate Quality Selection**: Choose between **320 kbps (HQ Studio)**, **192 kbps (Balanced)**, or **128 kbps (Space Saver)**.
- **Dedicated Playlist Folders**: Every downloaded playlist is stored in its own clean, dedicated folder on disk.
- **Cross-Playlist Deduplication**: Automatically detects if a song already exists in another downloaded playlist folder to skip redundant downloads and save time.
- **One-Click ZIP Export**: Download the entire playlist bundled into a clean `.zip` archive ready to extract.

---

## Tech Stack

### Backend

- **Python 3.10+** & **[FastAPI](https://fastapi.tiangolo.com/)** – High-performance asynchronous REST API
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** – Audio stream extraction engine
- **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** – YouTube Music catalog search
- **[Mutagen](https://mutagen.readthedocs.io/)** – ID3v2.3 tag injection and cover art embedding
- **[RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)** – Fast string matching and similarity scoring
- **[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)** – Self-contained FFmpeg binary for MP3 transcoding

### Frontend

- **[React](https://react.dev/)** + **[TypeScript](https://www.typescriptlang.org/)**
- **[Vite](https://vitejs.dev/)** – Fast build tooling and dev server
- **[Tailwind CSS](https://tailwindcss.com/)** – Neumorphic styling and responsive design
- **[Lucide React](https://lucide.dev/)** – Icons

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (only required if you want to develop the React frontend)
- **FFmpeg** (automatically detected via `imageio-ffmpeg` or your system PATH)

---

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jennyeuu/spotiloader.git
   cd spotiloader
   ```

2. **Set up a Python environment and install dependencies:**

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

---

### Running the App

#### Quick Start (All-in-One)

FastAPI automatically serves the pre-built React frontend:

```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser and navigate to **[http://localhost:8000](http://localhost:8000)**.

#### Frontend Development Mode

If you want to edit or customize the React UI with hot-reloading:

```bash
# In a separate terminal:
cd frontend
npm install
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**.

---

## 🙏 Credits & Acknowledgments

- Huge thanks to **[angall1/CSVMusic](https://github.com/angall1/CSVMusic)** for the inspiration and foundation on matching Spotify track metadata with YouTube Music sources.
- Thanks to the teams behind **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** and **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** for providing reliable audio fetching utilities.

---

## Disclaimer

Spotiloader is intended for personal archival and offline listening purposes for music you have access to. Please respect copyright laws and artist rights in your jurisdiction.
