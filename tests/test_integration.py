"""End-to-end downloads through the real yt-dlp and FFmpeg.

The media is generated locally with FFmpeg and served from a throw-away HTTP
server on 127.0.0.1, so no third-party content or internet access is needed.
"""

import functools
import http.server
import os
import socket
import subprocess
import tempfile
import threading
import unittest

import _bootstrap  # noqa: F401
from kdownloader import engine, system
from kdownloader.engine import DownloadItem, DownloadManager, Status

FFMPEG = system.find_ffmpeg()


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(FFMPEG, "FFmpeg is not available")
class RealDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.media = os.path.join(cls.tmp.name, "media")
        os.makedirs(cls.media)
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=15",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-shortest", os.path.join(cls.media, "clip.mp4")]
        if subprocess.run(cmd).returncode != 0:
            raise unittest.SkipTest("this FFmpeg build can't generate the test clip")
        handler = functools.partial(_Quiet, directory=cls.media)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def run_download(self, preset, url=None, retry_delays=(0.0, 0.0), dest=None):
        dest = dest or tempfile.mkdtemp(dir=self.tmp.name)
        events = []
        manager = DownloadManager(lambda k, p: events.append((k, p)), ffmpeg_path=FFMPEG,
                                  retry_delays=retry_delays, min_free_bytes=1)
        url = url or f"http://127.0.0.1:{self.port}/clip.mp4"
        manager.enqueue([DownloadItem(video_id="clip", title="clip", url=url, preset_id=preset, dest_dir=dest)])
        self.assertTrue(manager.wait_idle(60))
        return manager.snapshot()[0], events, dest

    def test_fetch_video_info(self):
        info = engine.fetch_video(f"http://127.0.0.1:{self.port}/clip.mp4")
        self.assertTrue(info.title)
        self.assertEqual(info.video_id, "clip")

    def test_mp4_download(self):
        done, events, _ = self.run_download("mp4_360")
        self.assertEqual(done.status, Status.COMPLETED, done.error)
        self.assertTrue(done.filepath.endswith(".mp4") and os.path.getsize(done.filepath) > 1000)
        self.assertIn("[clip]", os.path.basename(done.filepath))

    def test_mp3_conversion(self):
        done, _, dest = self.run_download("mp3_192")
        self.assertEqual(done.status, Status.COMPLETED, done.error)
        self.assertTrue(done.filepath.endswith(".mp3") and os.path.getsize(done.filepath) > 1000)

    def test_second_run_does_not_redownload(self):
        first, _, dest = self.run_download("mp3_128")
        self.assertEqual(first.status, Status.COMPLETED, first.error)
        before = os.path.getmtime(first.filepath)
        again, _, _ = self.run_download("mp3_128", dest=dest)
        self.assertEqual(again.status, Status.SKIPPED)
        self.assertEqual(os.path.getmtime(first.filepath), before)   # untouched

    def test_missing_file_fails_cleanly(self):
        done, _, _ = self.run_download("mp4_360", url=f"http://127.0.0.1:{self.port}/does-not-exist.mp4")
        self.assertEqual(done.status, Status.FAILED)
        self.assertTrue(done.error)

    def test_unreachable_server_reports_network_problem(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]          # nothing listens here
        done, _, _ = self.run_download("mp4_360", url=f"http://127.0.0.1:{port}/clip.mp4")
        self.assertEqual(done.status, Status.FAILED)
        self.assertEqual(done.error_code, "network", done.error)


if __name__ == "__main__":
    unittest.main()
