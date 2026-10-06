// Spotiloader Client Logic
let currentJobId = null;
let pollInterval = null;
let selectedBitrate = "320k";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initQualitySelector();
  initUrlForm();
  initCsvDropzone();
  initExamples();
});

// Toast System
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === "error" ? "⚠️" : type === "success" ? "✅" : "ℹ️"}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      
      tab.classList.add("active");
      const targetPanel = document.getElementById(tab.dataset.tab);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

// Quality & Compression Selector
function initQualitySelector() {
  const qualityButtons = document.querySelectorAll(".quality-option-btn");
  qualityButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      qualityButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedBitrate = btn.dataset.bitrate || "320k";
      if (selectedBitrate === "128k") {
        showToast("Storage Saver Mode enabled: Compressing audio to 128 kbps (~60% smaller file size)", "info");
      }
    });
  });
}

// Quick Example Tags
function initExamples() {
  const exampleTags = document.querySelectorAll(".example-tag");
  const urlInput = document.getElementById("spotify-url-input");
  exampleTags.forEach((tag) => {
    tag.addEventListener("click", () => {
      urlInput.value = tag.dataset.url;
      urlInput.focus();
    });
  });
}

// URL Form Submission
function initUrlForm() {
  const form = document.getElementById("url-form");
  const submitBtn = document.getElementById("url-submit-btn");
  const urlInput = document.getElementById("spotify-url-input");
  const skipToggle = document.getElementById("skip-existing-toggle");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) {
      showToast("Please enter a Spotify playlist, album, or track URL", "error");
      return;
    }

    setLoading(submitBtn, true, "Extracting...");

    try {
      const response = await fetch("/api/playlist/submit-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          url,
          skip_existing: skipToggle ? skipToggle.checked : true,
          bitrate: selectedBitrate,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to submit playlist.");
      }

      showToast(`Found "${data.playlist_title}" (${data.total_tracks} tracks). Download started!`, "success");
      startJobMonitor(data.job_id, data.playlist_title, data.total_tracks, data.bitrate);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoading(submitBtn, false, "Download Playlist");
    }
  });
}

// CSV Dropzone & Submission
function initCsvDropzone() {
  const dropzone = document.getElementById("csv-dropzone");
  const fileInput = document.getElementById("csv-file-input");
  const fileInfo = document.getElementById("csv-file-info");
  const submitBtn = document.getElementById("csv-submit-btn");
  const playlistNameInput = document.getElementById("csv-playlist-name");
  const skipToggle = document.getElementById("skip-existing-toggle");
  let selectedFile = null;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) {
      handleFile(e.target.files[0]);
    }
  });

  function handleFile(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      showToast("Please select a valid .csv file", "error");
      return;
    }
    selectedFile = file;
    fileInfo.innerHTML = `📄 <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)`;
    fileInfo.style.display = "inline-flex";
    if (!playlistNameInput.value) {
      playlistNameInput.value = file.name.replace(/\.[^/.]+$/, "");
    }
    submitBtn.disabled = false;
  }

  submitBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    setLoading(submitBtn, true, "Processing CSV...");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("playlist_name", playlistNameInput.value.trim() || "Imported CSV Playlist");
    formData.append("skip_existing", skipToggle ? skipToggle.checked : true);
    formData.append("bitrate", selectedBitrate);

    try {
      const response = await fetch("/api/playlist/submit-csv", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to parse CSV file.");
      }

      showToast(`Parsed "${data.playlist_title}" (${data.total_tracks} tracks). Download started!`, "success");
      startJobMonitor(data.job_id, data.playlist_title, data.total_tracks, data.bitrate);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoading(submitBtn, false, "Start Download");
    }
  });
}

function setLoading(btn, isLoading, text) {
  btn.disabled = isLoading;
  btn.innerHTML = isLoading ? `<span class="spinner">⏳</span> ${text}` : text;
}

// Job Progress Monitor
function startJobMonitor(jobId, title, totalTracks, bitrate) {
  currentJobId = jobId;
  if (pollInterval) clearInterval(pollInterval);

  const jobSection = document.getElementById("job-section");
  jobSection.classList.add("active");
  jobSection.scrollIntoView({ behavior: "smooth" });

  document.getElementById("job-playlist-title").textContent = title;
  document.getElementById("job-total-tracks").textContent = `${totalTracks} tracks`;
  document.getElementById("job-bitrate-badge").textContent = `${bitrate || selectedBitrate} Audio`;
  document.getElementById("btn-download-zip").href = `/api/playlist/download-zip/${jobId}`;

  pollJobStatus();
  pollInterval = setInterval(pollJobStatus, 1500);
}

async function pollJobStatus() {
  if (!currentJobId) return;

  try {
    const res = await fetch(`/api/playlist/status/${currentJobId}`);
    if (!res.ok) return;

    const data = await res.json();
    renderJobProgress(data);

    if (data.status === "SUCCESS" || data.status === "PARTIAL_SUCCESS" || data.status === "FAILURE") {
      clearInterval(pollInterval);
      if (data.status === "SUCCESS") {
        showToast("All playlist tracks processed and tagged!", "success");
      }
    }
  } catch (e) {
    console.error("Polling error:", e);
  }
}

function renderJobProgress(data) {
  // Update Status Pill
  const statusBadge = document.getElementById("job-status-badge");
  statusBadge.textContent = data.status;
  statusBadge.className = `badge-status ${data.status}`;

  // Update Bitrate Badge
  const bitrateBadge = document.getElementById("job-bitrate-badge");
  if (bitrateBadge && data.bitrate) {
    bitrateBadge.textContent = `${data.bitrate} MP3`;
  }

  // Update Progress Bar
  const percent = data.progress_percentage || 0;
  document.getElementById("progress-percentage-text").textContent = `${percent.toFixed(0)}%`;
  document.getElementById("progress-count-text").textContent = `${data.completed_tracks}/${data.total_tracks} completed`;
  document.getElementById("progress-fill").style.width = `${percent}%`;

  // Update Active Track Banner
  const currentBanner = document.getElementById("current-track-banner");
  const currentText = document.getElementById("current-track-name");
  if (data.current_track && data.status === "PROGRESS") {
    currentBanner.style.display = "flex";
    currentText.textContent = data.current_track;
  } else {
    currentBanner.style.display = "none";
  }

  // Show ZIP download button if completed > 0
  const zipBtn = document.getElementById("btn-download-zip");
  if (data.completed_tracks > 0) {
    zipBtn.style.display = "inline-flex";
  }

  // Render Tracks Table
  renderTracksTable(data.tracks_detail);
}

function renderTracksTable(tracks) {
  const tbody = document.getElementById("tracks-tbody");
  tbody.innerHTML = "";

  if (!tracks || tracks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Matching and downloading tracks in background...</td></tr>`;
    return;
  }

  tracks.forEach((track, idx) => {
    const tr = document.createElement("tr");

    // Score Badge
    let scoreBadge = `<span style="color: var(--text-dim)">-</span>`;
    if (track.cached) {
      scoreBadge = `<span class="score-badge cached">⚡ Cached</span>`;
    } else if (track.match_score !== null && track.match_score !== undefined) {
      const s = Math.round(track.match_score);
      const scoreClass = s >= 80 ? "high" : s >= 60 ? "medium" : "low";
      scoreBadge = `<span class="score-badge ${scoreClass}">${s}% Match</span>`;
    }

    // Status Badge
    let statusIcon = "⏳";
    let statusText = "In Progress";
    let statusClass = "in_progress";

    if (track.status === "completed") {
      if (track.cached) {
        statusIcon = "⚡";
        statusText = "Reused File";
        statusClass = "cached";
      } else {
        statusIcon = "✅";
        statusText = "Completed";
        statusClass = "completed";
      }
    } else if (track.status === "failed") {
      statusIcon = "❌";
      statusText = "Failed";
      statusClass = "failed";
    }

    // Download Action
    let actionBtn = "";
    if (track.status === "completed" && track.file_path) {
      actionBtn = `
        <a href="/api/playlist/download-track?file_path=${encodeURIComponent(track.file_path)}" 
           class="btn-icon-download" 
           title="Download MP3" download>
          ⬇️ MP3
        </a>
      `;
    } else if (track.status === "failed") {
      actionBtn = `<span style="font-size: 0.75rem; color: var(--status-failed);" title="${track.error || 'Error'}">Error</span>`;
    }

    tr.innerHTML = `
      <td class="track-number">${idx + 1}</td>
      <td class="track-info-cell">
        <div class="track-title">${escapeHtml(track.title)}</div>
        <div class="track-artist">${escapeHtml(track.artist)}</div>
      </td>
      <td>
        <div style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(track.matched_title || "-")}</div>
      </td>
      <td>${scoreBadge}</td>
      <td>
        <span class="status-badge ${statusClass}">
          <span>${statusIcon}</span> ${statusText}
        </span>
      </td>
      <td style="text-align: right;">${actionBtn}</td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[m]));
}
