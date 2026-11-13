"""Download format presets and their yt-dlp options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

VIDEO = "video"
AUDIO = "audio"


@dataclass(frozen=True)
class FormatPreset:
    id: str
    label: str
    kind: str
    max_height: Optional[int] = None
    mp3_bitrate: Optional[int] = None
    needs_ffmpeg: bool = False


VIDEO_PRESETS = (
    FormatPreset("mp4_360", "MP4 up to 360p", VIDEO, max_height=360),
    FormatPreset("mp4_480", "MP4 up to 480p", VIDEO, max_height=480),
    FormatPreset("mp4_720", "MP4 up to 720p", VIDEO, max_height=720),
    FormatPreset("mp4_1080", "MP4 up to 1080p", VIDEO, max_height=1080),
    FormatPreset("best_video", "Best available quality", VIDEO),
)

AUDIO_PRESETS = (
    FormatPreset("mp3_128", "MP3 128 kbps", AUDIO, mp3_bitrate=128, needs_ffmpeg=True),
    FormatPreset("mp3_192", "MP3 192 kbps", AUDIO, mp3_bitrate=192, needs_ffmpeg=True),
    FormatPreset("mp3_320", "MP3 320 kbps", AUDIO, mp3_bitrate=320, needs_ffmpeg=True),
    FormatPreset("best_audio", "Best available audio", AUDIO),
)

ALL_PRESETS: Dict[str, FormatPreset] = {p.id: p for p in VIDEO_PRESETS + AUDIO_PRESETS}

DEFAULT_VIDEO_PRESET = "mp4_1080"
DEFAULT_AUDIO_PRESET = "mp3_192"


def presets_for(kind: str, ffmpeg_available: bool) -> List[FormatPreset]:
    """Presets to offer for *kind*. Conversion options need FFmpeg."""
    source = VIDEO_PRESETS if kind == VIDEO else AUDIO_PRESETS
    return [p for p in source if ffmpeg_available or not p.needs_ffmpeg]


def get_preset(preset_id: str) -> FormatPreset:
    return ALL_PRESETS.get(preset_id) or ALL_PRESETS[DEFAULT_VIDEO_PRESET]


def is_valid_preset(preset_id: object, kind: Optional[str] = None) -> bool:
    preset = ALL_PRESETS.get(preset_id) if isinstance(preset_id, str) else None
    return preset is not None and (kind is None or preset.kind == kind)


def build_options(preset: FormatPreset, ffmpeg_path: Optional[str]) -> dict:
    """yt-dlp options that select and convert media for *preset*.

    Without FFmpeg only single-file (progressive) formats are requested and no
    conversion is attempted.
    """
    opts: dict = {}
    have_ffmpeg = bool(ffmpeg_path)
    if have_ffmpeg:
        opts["ffmpeg_location"] = ffmpeg_path

    if preset.kind == VIDEO:
        if preset.max_height:
            h = preset.max_height
            if have_ffmpeg:
                opts["format"] = (
                    f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/"
                    f"b[height<={h}]/w"
                )
                opts["merge_output_format"] = "mp4"
            else:
                opts["format"] = f"b[height<={h}][ext=mp4]/b[height<={h}]/w"
        else:
            if have_ffmpeg:
                opts["format"] = "bv*+ba/b"
                opts["merge_output_format"] = "mp4"
            else:
                opts["format"] = "b"
    else:
        opts["format"] = "bestaudio/best"
        if preset.mp3_bitrate and have_ffmpeg:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(preset.mp3_bitrate),
            }]
    return opts
