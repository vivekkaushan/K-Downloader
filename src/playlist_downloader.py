#!/usr/bin/env python3
"""Playlist Downloader V2 — modern cross-platform desktop UI."""

import os
import queue
import threading
import webbrowser
import sys
import json
from pathlib import Path
from PIL import Image
import imageio_ffmpeg
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

import customtkinter as ctk
import yt_dlp


APP_NAME = "K Downloader"


class PlaylistDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self.geometry("1180x780")
        self.minsize(980, 680)
        self.configure(fg_color="#0d081e")

        self.events = queue.Queue()
        self.entries = []
        self.selected = set()
        self.downloading = False
        self.cancel_event = threading.Event()
        self.filter_var = ctk.StringVar()
        self.url_var = ctk.StringVar()
        self.folder_var = ctk.StringVar(value=str(Path.home() / "Downloads" / "YouTube"))
        self.format_var = ctk.StringVar(value="1080p · MP4")
        self.status_var = ctk.StringVar(value="Paste a playlist link to get started.")
        self.current_var = ctk.StringVar(value="Waiting for playlist")
        self.total_progress = 0
        self.row_widgets = []

        self._build_ui()
        self.withdraw()
        self.after(180, self._show_first_run_welcome)
        self.after(100, self._poll_events)

    def _welcome_state_file(self):
        # Store only the user's acknowledgement locally; no Facebook account data is collected.
        return Path.home() / ".k_downloader" / "welcome_acknowledged.json"

    def _show_first_run_welcome(self):
        state_file = self._welcome_state_file()
        try:
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding="utf-8"))
                if state.get("acknowledged") is True:
                    self.deiconify()
                    return
        except Exception:
            pass

        win = ctk.CTkToplevel(self)
        win.title("Welcome to K Downloader")
        win.geometry("470x590")
        win.resizable(False, False)
        win.configure(fg_color="#0d081e")
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", self.destroy)
        win.grab_set()

        card = ctk.CTkFrame(win, fg_color="#1a1033", corner_radius=20)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        logo_file = bundle_root / "k_downloader_logo.png"
        try:
            welcome_logo = ctk.CTkImage(light_image=Image.open(logo_file),
                                        dark_image=Image.open(logo_file), size=(112, 112))
            ctk.CTkLabel(card, image=welcome_logo, text="").pack(pady=(26, 8))
            # Keep a reference alive for Tk image rendering.
            win._welcome_logo = welcome_logo
        except Exception:
            ctk.CTkLabel(card, text="K", font=ctk.CTkFont(size=56, weight="bold"),
                         text_color="#ffffff").pack(pady=(26, 8))

        ctk.CTkLabel(card, text="Welcome to K Downloader",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#ffffff").pack(pady=(4, 5))
        ctk.CTkLabel(card, text="POWERED BY KAUSHAN",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#c29aff").pack(pady=(0, 18))

        ctk.CTkLabel(
            card,
            text="Enjoying K Downloader? Support future updates and free tools by following KAUSHAN on Facebook.",
            wraplength=370, justify="center",
            font=ctk.CTkFont(size=13), text_color="#d6cce5"
        ).pack(padx=28, pady=(0, 18))

        ctk.CTkButton(
            card, text="f   Follow KAUSHAN on Facebook",
            height=44, corner_radius=10, fg_color="#523078", hover_color="#684092",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: webbrowser.open("https://www.facebook.com/KaushanOfficial")
        ).pack(fill="x", padx=34, pady=(0, 16))

        ctk.CTkLabel(
            card,
            text="After visiting the page, confirm below to continue.",
            font=ctk.CTkFont(size=11), text_color="#a995c2"
        ).pack(pady=(0, 8))

        acknowledged = ctk.BooleanVar(value=False)
        confirm = ctk.CTkCheckBox(
            card,
            text="I've followed or supported KAUSHAN",
            variable=acknowledged,
            checkbox_width=20, checkbox_height=20,
            font=ctk.CTkFont(size=12), text_color="#eee7f7",
            fg_color="#7546a8", hover_color="#9564c2",
            command=lambda: continue_btn.configure(
                state="normal" if acknowledged.get() else "disabled"
            )
        )
        confirm.pack(pady=(0, 14))

        ctk.CTkLabel(
            card,
            text="Facebook does not provide this app with a way to verify follows. This is an honour-system confirmation.",
            wraplength=370, justify="center",
            font=ctk.CTkFont(size=10), text_color="#8f7ba8"
        ).pack(padx=24, pady=(0, 16))

        def continue_to_app():
            try:
                state_file.parent.mkdir(parents=True, exist_ok=True)
                state_file.write_text(
                    json.dumps({"acknowledged": True}, indent=2),
                    encoding="utf-8"
                )
            except Exception:
                # If local preferences cannot be saved, still allow this session to continue.
                pass
            win.grab_release()
            win.destroy()
            self.deiconify()
            self.lift()

        continue_btn = ctk.CTkButton(
            card, text="Continue to K Downloader",
            height=42, corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled", command=continue_to_app
        )
        continue_btn.pack(fill="x", padx=34, pady=(0, 24))

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        side = ctk.CTkFrame(self, width=224, corner_radius=0, fg_color="#130b2b")
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        brand_row = ctk.CTkFrame(side, fg_color="transparent")
        brand_row.pack(anchor="w", padx=18, pady=(22, 4))
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        logo_file = bundle_root / "k_downloader_logo.png"
        self.brand_logo = ctk.CTkImage(light_image=Image.open(logo_file),
                                       dark_image=Image.open(logo_file), size=(48, 48))
        ctk.CTkLabel(brand_row, image=self.brand_logo, text="").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(brand_row, text="K Downloader", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(side, text="PLAYLIST DOWNLOADER", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#a78bc9").pack(anchor="w", padx=24, pady=(0, 28))
        self._nav_item(side, "▦", "Playlist", True)
        self._nav_item(side, "⇩", "Downloads", False)
        self._nav_item(side, "⚙", "Settings", False)
        ctk.CTkFrame(side, height=2, fg_color="#26334d").pack(fill="x", padx=20, pady=22)
        ctk.CTkLabel(side, text="QUICK GUIDE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#64748b").pack(anchor="w", padx=22, pady=(0, 10))
        for line in ("1. Paste a playlist URL", "2. Fetch and select videos", "3. Choose quality", "4. Download to your folder"):
            ctk.CTkLabel(side, text=line, font=ctk.CTkFont(size=11), text_color="#aab6ca").pack(
                anchor="w", padx=22, pady=5)
        side_bottom = ctk.CTkFrame(side, fg_color="transparent")
        side_bottom.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(side_bottom, text="POWERED BY KAUSHAN", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#c29aff").pack(anchor="w")
        ctk.CTkButton(side_bottom, text="f  Follow on Facebook ↗", height=34,
                      fg_color="#352052", hover_color="#523078", corner_radius=8,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=lambda: webbrowser.open("https://www.facebook.com/KaushanOfficial")).pack(
                          fill="x", pady=(9, 8))
        ctk.CTkLabel(side_bottom, text="facebook.com/KaushanOfficial", wraplength=180,
                     font=ctk.CTkFont(size=9), text_color="#8f7ba8").pack(anchor="w")
        ctk.CTkLabel(side_bottom, text="Use only where you have permission.", wraplength=180,
                     font=ctk.CTkFont(size=9), text_color="#64748b").pack(anchor="w", pady=(10, 0))

        # Main content
        main = ctk.CTkFrame(self, fg_color="#0d081e", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Your playlist library", font=ctk.CTkFont(size=27, weight="bold"),
                     text_color="#f8fafc").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(top, text="Download playlists with K Downloader · Powered by KAUSHAN.",
                     font=ctk.CTkFont(size=12), text_color="#94a3b8").grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.theme_button = ctk.CTkButton(top, text="☾  Dark", width=90, height=32,
                                          fg_color="#1b2942", hover_color="#293b5c",
                                          command=self._toggle_theme)
        self.theme_button.grid(row=0, column=1, rowspan=2, sticky="e")

        # URL card
        url_card = ctk.CTkFrame(main, fg_color="#1a1033", corner_radius=16)
        url_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        url_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(url_card, text="YOUTUBE PLAYLIST URL", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").grid(row=0, column=0, sticky="w", padx=18, pady=(15, 6))
        urlrow = ctk.CTkFrame(url_card, fg_color="transparent")
        urlrow.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        urlrow.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(urlrow, textvariable=self.url_var, height=43,
                                      placeholder_text="https://www.youtube.com/playlist?list=…",
                                      corner_radius=10, border_color="#49356f", fg_color="#100a22")
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.fetch_btn = ctk.CTkButton(urlrow, text="↧  Fetch playlist", height=43, width=160,
                                       corner_radius=10, font=ctk.CTkFont(weight="bold"),
                                       command=self.fetch_playlist)
        self.fetch_btn.grid(row=0, column=1)

        # Summary cards
        stats = ctk.CTkFrame(main, fg_color="transparent")
        stats.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        for i in range(3):
            stats.grid_columnconfigure(i, weight=1)
        self.stat_total = self._stat_card(stats, 0, "PLAYLIST VIDEOS", "0", "▤")
        self.stat_selected = self._stat_card(stats, 1, "SELECTED", "0", "✓")
        self.stat_done = self._stat_card(stats, 2, "DOWNLOADED", "0", "⇩")

        # Playlist panel
        panel = ctk.CTkFrame(main, fg_color="#1a1033", corner_radius=16)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        ctk.CTkLabel(bar, text="Playlist videos", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#f8fafc").pack(side="left")
        self.search_entry = ctk.CTkEntry(bar, width=210, height=32, textvariable=self.filter_var,
                                         placeholder_text="⌕  Search videos…", corner_radius=9)
        self.search_entry.pack(side="right")
        self.filter_var.trace_add("write", lambda *_: self._render_rows())

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        ctk.CTkButton(actions, text="Select all", width=90, height=30, fg_color="#352052",
                      hover_color="#523078", command=self.select_all).pack(side="left")
        ctk.CTkButton(actions, text="Clear", width=70, height=30, fg_color="#352052",
                      hover_color="#523078", command=self.select_none).pack(side="left", padx=7)
        self.list_count = ctk.CTkLabel(actions, text="No playlist loaded", text_color="#94a3b8",
                                       font=ctk.CTkFont(size=11))
        self.list_count.pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(panel, fg_color="#100a22", corner_radius=10)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(self.list_frame, text="Your playlist videos will appear here.",
                                        text_color="#64748b", font=ctk.CTkFont(size=13))
        self.empty_label.grid(row=0, column=0, pady=45)

        # Download controls
        bottom = ctk.CTkFrame(main, fg_color="#1a1033", corner_radius=16)
        bottom.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        bottom.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bottom, text="QUALITY", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").grid(row=0, column=0, sticky="w", padx=16, pady=(13, 4))
        self.quality_menu = ctk.CTkOptionMenu(
            bottom, variable=self.format_var, values=["Best available", "1080p · MP4", "720p · MP4", "Audio · MP3"],
            width=150, height=34, fg_color="#352052", button_color="#7546a8",
            dropdown_fg_color="#21133d"
        )
        self.quality_menu.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(bottom, text="SAVE LOCATION", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").grid(row=0, column=1, sticky="w", padx=10, pady=(13, 4))
        folderrow = ctk.CTkFrame(bottom, fg_color="transparent")
        folderrow.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 14))
        folderrow.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(folderrow, textvariable=self.folder_var, height=34, corner_radius=8,
                     fg_color="#100a22", border_color="#49356f").grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(folderrow, text="Browse", width=75, height=34, fg_color="#352052",
                      hover_color="#523078", command=self.choose_folder).grid(row=0, column=1, padx=(7, 0))
        self.download_btn = ctk.CTkButton(bottom, text="↓  Download selected", width=190, height=43,
                                          corner_radius=10, font=ctk.CTkFont(weight="bold"),
                                          command=self.start_downloads, state="disabled")
        self.download_btn.grid(row=0, column=2, rowspan=2, padx=16, pady=12)
        self.stop_btn = ctk.CTkButton(bottom, text="Stop", width=70, height=43, corner_radius=10,
                                      fg_color="#5b2b70", hover_color="#78409b",
                                      command=self.stop_downloads, state="disabled")
        self.stop_btn.grid(row=0, column=3, rowspan=2, padx=(0, 16), pady=12)

        # Progress footer
        progress_card = ctk.CTkFrame(main, fg_color="transparent")
        progress_card.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        progress_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(progress_card, textvariable=self.current_var, text_color="#cbd5e1",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.percent_label = ctk.CTkLabel(progress_card, text="0%", text_color="#c29aff",
                                          font=ctk.CTkFont(size=11, weight="bold"))
        self.percent_label.grid(row=0, column=1, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(progress_card, height=8, corner_radius=8,
                                               progress_color="#a56be8", fg_color="#382052")
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        self.progress_bar.set(0)
        ctk.CTkLabel(progress_card, textvariable=self.status_var, text_color="#64748b",
                     font=ctk.CTkFont(size=10)).grid(row=2, column=0, columnspan=2, sticky="w")

    def _nav_item(self, parent, symbol, label, active):
        color = "#1d3b68" if active else "transparent"
        fg = "#eaf2ff" if active else "#94a3b8"
        item = ctk.CTkFrame(parent, fg_color=color, corner_radius=9)
        item.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(item, text=symbol, width=30, text_color=fg,
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(10, 0), pady=10)
        ctk.CTkLabel(item, text=label, text_color=fg,
                     font=ctk.CTkFont(size=12, weight="bold" if active else "normal")).pack(
            side="left", padx=5, pady=10)

    def _stat_card(self, parent, col, label, value, symbol):
        card = ctk.CTkFrame(parent, fg_color="#1a1033", corner_radius=13)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 7, 7 if col < 2 else 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=label, text_color="#94a3b8",
                     font=ctk.CTkFont(size=9, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        val = ctk.CTkLabel(card, text=value, text_color="#f8fafc",
                           font=ctk.CTkFont(size=23, weight="bold"))
        val.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        ctk.CTkLabel(card, text=symbol, text_color="#c29aff",
                     font=ctk.CTkFont(size=19)).grid(row=0, column=1, rowspan=2, padx=14)
        return val

    def _toggle_theme(self):
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode == "Dark" else "dark")
        self.theme_button.configure(text="☀  Light" if mode == "Dark" else "☾  Dark")

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def fetch_playlist(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showinfo(APP_NAME, "Paste a playlist URL first.")
            return
        if self.downloading:
            return
        self.fetch_btn.configure(state="disabled", text="Loading…")
        self.status_var.set("Connecting to YouTube and reading playlist details…")
        self.empty_label.configure(text="Loading playlist…")
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url):
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                    "extract_flat": "in_playlist", "ignoreerrors": True, "playlistend": 10000}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = []
            for item in (info or {}).get("entries") or []:
                if not item:
                    continue
                vid = item.get("id")
                link = item.get("webpage_url") or item.get("url")
                if not link or not str(link).startswith(("http://", "https://")):
                    link = f"https://www.youtube.com/watch?v={vid}" if vid else None
                if link:
                    entries.append({"id": vid or "", "url": link,
                                    "title": item.get("title") or "Untitled video",
                                    "duration": item.get("duration"), "status": "Ready"})
            self.events.put(("fetched", entries, None))
        except Exception as exc:
            self.events.put(("fetched", [], str(exc)))

    @staticmethod
    def _duration(seconds):
        if seconds is None:
            return "—"
        try:
            n = int(seconds)
            return f"{n//3600:02d}:{(n%3600)//60:02d}:{n%60:02d}" if n >= 3600 else f"{n//60:02d}:{n%60:02d}"
        except (ValueError, TypeError):
            return "—"

    def _render_rows(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.row_widgets = []
        query = self.filter_var.get().lower().strip()
        visible = [(i, item) for i, item in enumerate(self.entries)
                   if query in item["title"].lower()]
        if not visible:
            ctk.CTkLabel(self.list_frame, text="No matching videos." if self.entries else
                         "Your playlist videos will appear here.", text_color="#64748b").grid(
                row=0, column=0, pady=45)
        for row, (idx, item) in enumerate(visible):
            bg = "#15223a" if row % 2 == 0 else "#111c30"
            line = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=8)
            line.grid(row=row, column=0, sticky="ew", padx=4, pady=3)
            line.grid_columnconfigure(2, weight=1)
            var = ctk.BooleanVar(value=idx in self.selected)
            cb = ctk.CTkCheckBox(line, text="", width=25, variable=var, checkbox_width=18,
                                 checkbox_height=18, command=lambda i=idx, v=var: self._toggle_item(i, v))
            cb.grid(row=0, column=0, padx=(10, 7), pady=10)
            ctk.CTkLabel(line, text=f"{idx+1:02d}", width=36, text_color="#64748b",
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1)
            ctk.CTkLabel(line, text=item["title"], anchor="w", text_color="#e2e8f0",
                         font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="ew", padx=8)
            ctk.CTkLabel(line, text=self._duration(item["duration"]), width=62,
                         text_color="#94a3b8", font=ctk.CTkFont(size=10)).grid(row=0, column=3, padx=8)
            status_color = "#4ade80" if item["status"] == "Complete" else "#fbbf24" if item["status"] in ("Downloading", "Queued") else "#94a3b8"
            ctk.CTkLabel(line, text=item["status"], width=95, text_color=status_color,
                         font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=4, padx=(4, 12))
        self._update_stats()

    def _toggle_item(self, idx, var):
        if var.get():
            self.selected.add(idx)
        else:
            self.selected.discard(idx)
        self._update_stats()

    def select_all(self):
        self.selected = set(range(len(self.entries)))
        self._render_rows()

    def select_none(self):
        self.selected.clear()
        self._render_rows()

    def _update_stats(self):
        self.stat_total.configure(text=str(len(self.entries)))
        self.stat_selected.configure(text=str(len(self.selected)))
        self.stat_done.configure(text=str(sum(1 for x in self.entries if x["status"] == "Complete")))
        self.list_count.configure(text=f"{len(self.entries)} videos · {len(self.selected)} selected")

    def start_downloads(self):
        if self.downloading:
            return
        chosen = [self.entries[i] for i in sorted(self.selected) if i < len(self.entries)]
        if not chosen:
            messagebox.showinfo(APP_NAME, "Select one or more videos to download.")
            return
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Cannot use save folder:\n{exc}")
            return
        self.cancel_event.clear()
        self.downloading = True
        self.download_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        for item in chosen:
            item["status"] = "Queued"
        self._render_rows()
        threading.Thread(target=self._download_worker, args=(chosen, str(folder), self.format_var.get()),
                         daemon=True).start()

    def stop_downloads(self):
        self.cancel_event.set()
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Stopping…")

    def _download_worker(self, chosen, folder, fmt):
        total = len(chosen)
        done = 0
        for n, item in enumerate(chosen, 1):
            if self.cancel_event.is_set():
                break
            self.events.put(("item", item, "Downloading"))
            self.events.put(("current", f"Downloading {n} of {total}: {item['title']}"))
            if fmt == "Audio · MP3":
                format_selector = "bestaudio/best"
                pp = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
                merge = None
            elif fmt == "720p · MP4":
                format_selector = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                pp, merge = [], "mp4"
            elif fmt == "1080p · MP4":
                format_selector = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
                pp, merge = [], "mp4"
            else:
                format_selector, pp, merge = "bv*+ba/b", [], "mp4"

            def hook(data, current=item):
                if self.cancel_event.is_set():
                    raise yt_dlp.utils.DownloadError("Stopped by user")
                if data.get("status") == "downloading":
                    d = data.get("downloaded_bytes") or 0
                    size = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    self.events.put(("item_progress", d / size if size else 0, current["title"]))
            options = {"format": format_selector,
                       "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
                       "outtmpl": os.path.join(folder, "%(title).180B [%(id)s].%(ext)s"),
                       "noplaylist": True, "continuedl": True, "overwrites": False,
                       "quiet": True, "no_warnings": True, "progress_hooks": [hook],
                       "postprocessors": pp, "windowsfilenames": True, "retries": 5,
                       "fragment_retries": 5}
            if merge:
                options["merge_output_format"] = merge
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([item["url"]])
                if self.cancel_event.is_set():
                    self.events.put(("item", item, "Stopped"))
                else:
                    done += 1
                    self.events.put(("item", item, "Complete"))
            except Exception as exc:
                self.events.put(("item", item, "Stopped" if self.cancel_event.is_set() else "Failed"))
                if not self.cancel_event.is_set():
                    self.events.put(("error", f"{item['title']}: {exc}"))
            self.events.put(("overall", done / total if total else 0))
        self.events.put(("finished", done, total, self.cancel_event.is_set()))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "fetched":
                    _, entries, error = event
                    self.fetch_btn.configure(state="normal", text="↧  Fetch playlist")
                    if error:
                        self.empty_label.configure(text="Could not load playlist. Check the URL or try again.")
                        self.status_var.set("Playlist could not be loaded.")
                        messagebox.showerror(APP_NAME, f"Could not fetch playlist:\n\n{error}")
                    else:
                        self.entries = entries
                        self.selected.clear()
                        self._render_rows()
                        self.download_btn.configure(state="normal" if entries else "disabled")
                        self.empty_label.configure(text="No videos found.")
                        self.status_var.set(f"Loaded {len(entries)} videos." if entries else "No videos found in this playlist.")
                        if not entries:
                            messagebox.showwarning(APP_NAME, "No videos were found. Check that the playlist is accessible and contains videos.")
                elif kind == "item":
                    _, item, status = event
                    item["status"] = status
                    self._render_rows()
                elif kind == "current":
                    self.current_var.set(event[1])
                elif kind == "item_progress":
                    _, fraction, title = event
                    self.current_var.set(f"{title} · current video {fraction*100:.1f}%")
                elif kind == "overall":
                    self.progress_bar.set(event[1])
                    self.percent_label.configure(text=f"{event[1]*100:.0f}%")
                elif kind == "error":
                    self.status_var.set("A video failed. Check its status and try again.")
                elif kind == "finished":
                    _, done, total, stopped = event
                    self.downloading = False
                    self.fetch_btn.configure(state="normal", text="↧  Fetch playlist")
                    self.download_btn.configure(state="normal" if self.entries else "disabled")
                    self.stop_btn.configure(state="disabled")
                    self.status_var.set(f"{'Stopped' if stopped else 'Finished'} · {done} of {total} videos downloaded.")
                    self.current_var.set("Download session complete" if not stopped else "Download session stopped")
                    self._update_stats()
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


if __name__ == "__main__":
    PlaylistDownloader().mainloop()
