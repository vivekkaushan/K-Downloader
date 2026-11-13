import json
import os
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from kdownloader import config, errors, formats, urls, utils
from kdownloader.history import HistoryStore
from kdownloader.updates import parse_version


class ConfigTests(unittest.TestCase):
    def test_defaults_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = config.SettingsStore(Path(tmp) / "s.json")
            s = store.load()
            self.assertEqual(s.theme, "dark")
            s.theme, s.default_kind, s.download_dir = "light", "audio", "/some/where"
            self.assertTrue(store.save(s))
            again = store.load()
            self.assertEqual((again.theme, again.default_kind, again.download_dir), ("light", "audio", "/some/where"))

    def test_invalid_values_fall_back(self):
        s = config.sanitize({"theme": "neon", "default_video_quality": "mp3_128", "max_history": 3,
                             "keep_history": "yes", "default_kind": 5, "unknown": 1})
        d = config.Settings()
        self.assertEqual((s.theme, s.default_video_quality, s.max_history, s.keep_history, s.default_kind),
                         (d.theme, d.default_video_quality, d.max_history, d.keep_history, d.default_kind))
        self.assertEqual(config.sanitize("garbage"), d)

    def test_corrupt_file_gives_defaults_and_keeps_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(config.SettingsStore(path).load(), config.Settings())
            self.assertTrue((Path(tmp) / "s.json.bad").exists())

    def test_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = config.SettingsStore(Path(tmp) / "s.json")
            s = store.load(); s.theme = "light"; store.save(s)
            self.assertEqual(store.reset(), config.Settings())
            self.assertEqual(store.load().theme, "dark")

    def test_welcome_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["KDOWNLOADER_HOME"] = tmp
            try:
                self.assertFalse(config.welcome_seen())
                config.mark_welcome_seen()
                self.assertTrue(config.welcome_seen())
                self.assertEqual(json.loads((Path(tmp) / "welcome_acknowledged.json").read_text()), {"acknowledged": True})
            finally:
                del os.environ["KDOWNLOADER_HOME"]


class FormatTests(unittest.TestCase):
    def test_required_presets_exist(self):
        labels = [p.label for p in formats.VIDEO_PRESETS + formats.AUDIO_PRESETS]
        for expected in ("MP4 up to 360p", "MP4 up to 480p", "MP4 up to 720p", "MP4 up to 1080p",
                         "Best available quality", "MP3 128 kbps", "MP3 192 kbps", "MP3 320 kbps",
                         "Best available audio"):
            self.assertIn(expected, labels)

    def test_conversion_options_need_ffmpeg(self):
        with_ff = [p.id for p in formats.presets_for("audio", True)]
        without = [p.id for p in formats.presets_for("audio", False)]
        self.assertEqual(without, ["best_audio"])
        self.assertIn("mp3_320", with_ff)

    def test_build_options(self):
        mp3 = formats.build_options(formats.get_preset("mp3_320"), "/ff")
        self.assertEqual(mp3["postprocessors"][0]["preferredquality"], "320")
        v = formats.build_options(formats.get_preset("mp4_720"), "/ff")
        self.assertIn("height<=720", v["format"]); self.assertEqual(v["merge_output_format"], "mp4")
        nov = formats.build_options(formats.get_preset("mp4_720"), None)
        self.assertNotIn("merge_output_format", nov); self.assertNotIn("+", nov["format"])
        self.assertNotIn("postprocessors", formats.build_options(formats.get_preset("best_audio"), "/ff"))
        self.assertEqual(formats.get_preset("nonsense").id, formats.DEFAULT_VIDEO_PRESET)


class UrlTests(unittest.TestCase):
    def test_playlist_urls(self):
        self.assertTrue(urls.check_playlist_url("https://www.youtube.com/playlist?list=PL123").ok)
        self.assertTrue(urls.check_playlist_url("youtube.com/watch?v=abc&list=PL123").ok)
        self.assertFalse(urls.check_playlist_url("").ok)
        self.assertFalse(urls.check_playlist_url("not a url").ok)
        self.assertFalse(urls.check_playlist_url("ftp://example.com/x").ok)
        self.assertFalse(urls.check_playlist_url("https://www.youtube.com/watch?v=abc").ok)
        self.assertFalse(urls.check_playlist_url("https://www.youtube.com/playlist?list=WL").ok)

    def test_video_urls(self):
        self.assertTrue(urls.check_video_url("https://youtu.be/dQw4w9WgXcQ").ok)
        self.assertTrue(urls.check_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ").ok)
        self.assertTrue(urls.check_video_url("https://www.youtube.com/shorts/abc").ok)
        self.assertFalse(urls.check_video_url("https://www.youtube.com/playlist?list=PL1").ok)
        self.assertFalse(urls.check_video_url("https://www.youtube.com/").ok)


class ErrorTests(unittest.TestCase):
    def test_classification(self):
        cases = {
            "ERROR: [youtube] abc: Private video. Sign in if you've been granted access": "private",
            "ERROR: [youtube] abc: Video unavailable": "unavailable",
            "ERROR: The uploader has not made this video available in your country": "region",
            "ERROR: Sign in to confirm your age": "login",
            "ERROR: Unable to download webpage: <urlopen error [Errno -3] Temporary failure in name resolution>": "network",
            "OSError: [Errno 28] No space left on device": "disk_full",
            "ERROR: Unsupported URL: https://example.com": "invalid_url",
            "HTTP Error 429: Too Many Requests": "rate_limit",
            "Stopped by user": "cancelled",
            "ERROR: ffprobe and ffmpeg not found": "ffmpeg",
            "something weird": "unknown",
        }
        for text, code in cases.items():
            self.assertEqual(errors.classify_error(text).code, code, text)
        self.assertTrue(errors.classify_error("timed out").retryable)
        self.assertFalse(errors.classify_error("Private video").retryable)


class HistoryTests(unittest.TestCase):
    def test_add_limit_remove_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = HistoryStore(Path(tmp) / "h.json", max_items=3)
            for i in range(5):
                h.add({"title": f"t{i}", "status": "Completed" if i % 2 == 0 else "Failed", "size": 10})
            items = h.all()
            self.assertEqual([r["title"] for r in items], ["t4", "t3", "t2"])
            self.assertEqual(h.stats(), {"completed": 2, "failed": 1, "bytes": 20})
            h.remove(items[0]["id"])
            self.assertEqual(len(HistoryStore(Path(tmp) / "h.json").all()), 2)   # persisted
            h.clear(); self.assertEqual(h.all(), [])

    def test_corrupt_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "h.json"; p.write_text("[1, 2", encoding="utf-8")
            self.assertEqual(HistoryStore(p).all(), [])


class UtilTests(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(utils.format_duration(65), "1:05")
        self.assertEqual(utils.format_duration(3725), "1:02:05")
        self.assertEqual(utils.format_duration(None), "—")
        self.assertEqual(utils.format_bytes(1536), "1.5 KB")
        self.assertEqual(utils.format_speed(None), "—")
        self.assertEqual(parse_version("v3.0.1"), (3, 0, 1))
        self.assertGreater(parse_version("v3.1.0"), parse_version("3.0.9"))


if __name__ == "__main__":
    unittest.main()
