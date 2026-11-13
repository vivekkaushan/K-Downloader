"""Speed features: simultaneous downloads and parallel fragments."""

import functools
import http.server
import os
import subprocess
import tempfile
import threading
import time
import unittest

import _bootstrap  # noqa: F401
from kdownloader import config, engine, system
from kdownloader.engine import DownloadItem, DownloadManager, Status
from test_engine import Collector, item, make_factory, write_file

FFMPEG = system.find_ffmpeg()


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = os.path.join(self.tmp.name, "out")
        self.col = Collector()
        self.lock = threading.Lock()
        self.running = 0
        self.peak = 0

    def tearDown(self):
        self.tmp.cleanup()

    def behavior(self, hold=0.3):
        def run(opts, url, n):
            with self.lock:
                self.running += 1
                self.peak = max(self.peak, self.running)
            try:
                time.sleep(hold)
                vid = url.rsplit("/", 1)[-1]
                path = write_file(self.dest, f"T [{vid}].mp4")
                return {"requested_downloads": [{"filepath": path}]}
            finally:
                with self.lock:
                    self.running -= 1
        return run

    def manager(self, behavior, **kw):
        kw.setdefault("min_free_bytes", 1)
        return DownloadManager(self.col, ffmpeg_path="/fake/ffmpeg", ydl_factory=make_factory(behavior), **kw)

    def test_runs_several_videos_at_once_up_to_the_limit(self):
        m = self.manager(self.behavior(), parallel=3)
        m.enqueue([item(self.dest, f"v{i}") for i in range(6)])
        self.assertTrue(m.wait_idle(20))
        self.assertEqual(self.peak, 3)
        self.assertEqual({i.status for i in m.snapshot()}, {Status.COMPLETED})
        self.assertEqual(self.col.kinds().count("idle"), 1)
        self.assertEqual(self.col.kinds()[-1], "idle")

    def test_one_at_a_time_when_parallel_is_1(self):
        m = self.manager(self.behavior(0.1), parallel=1)
        m.enqueue([item(self.dest, f"v{i}") for i in range(3)])
        self.assertTrue(m.wait_idle(20))
        self.assertEqual(self.peak, 1)

    def test_parallel_is_faster_than_sequential(self):
        def timed(parallel):
            self.col = Collector()
            m = self.manager(self.behavior(0.4), parallel=parallel)
            t0 = time.monotonic()
            m.enqueue([item(self.dest, f"p{parallel}_{i}") for i in range(4)])
            self.assertTrue(m.wait_idle(30))
            return time.monotonic() - t0
        self.assertLess(timed(4), timed(1) * 0.6)

    def test_limit_is_clamped_and_can_change_while_running(self):
        m = self.manager(self.behavior(0.2), parallel=99)
        self.assertEqual(m.parallel, engine.MAX_PARALLEL)
        m.set_parallel(0)
        self.assertEqual(m.parallel, 1)
        m.set_parallel(4)
        m.enqueue([item(self.dest, f"c{i}") for i in range(4)])
        time.sleep(0.05)
        m.set_parallel(1)   # running ones finish, nothing new starts beyond the limit
        self.assertTrue(m.wait_idle(20))
        self.assertEqual({i.status for i in m.snapshot()}, {Status.COMPLETED})

    def test_raising_the_limit_starts_waiting_items(self):
        m = self.manager(self.behavior(0.5), parallel=1)
        m.enqueue([item(self.dest, f"r{i}") for i in range(3)])
        time.sleep(0.1)
        m.set_parallel(3)
        self.assertTrue(m.wait_idle(20))
        self.assertEqual(self.peak, 3)

    def test_same_video_is_never_downloaded_twice_at_once(self):
        m = self.manager(self.behavior(0.3), parallel=3)
        a = item(self.dest, "same")
        b = item(self.dest, "same")
        b.preset_id = "mp3_192"          # different preset, same file stem
        m.enqueue([a, b])
        self.assertTrue(m.wait_idle(20))
        self.assertEqual(self.peak, 1)
        self.assertEqual(m.get(a.id).status, Status.COMPLETED)
        self.assertEqual(m.get(b.id).status, Status.SKIPPED)   # already saved by the first

    def test_cancelling_one_does_not_stop_the_others(self):
        started = threading.Event()
        hooks = {}

        def behavior(opts, url, n):
            vid = url.rsplit("/", 1)[-1]
            hook = opts["progress_hooks"][0]
            end = time.monotonic() + (30 if vid == "slow" else 0.5)
            started.set()
            while time.monotonic() < end:
                hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})
                time.sleep(0.02)
            return {"requested_downloads": [{"filepath": write_file(self.dest, f"T [{vid}].mp4")}]}
        m = self.manager(behavior, parallel=2)
        slow, fast = item(self.dest, "slow"), item(self.dest, "fast")
        m.enqueue([slow, fast])
        self.assertTrue(started.wait(5))
        time.sleep(0.1)
        m.cancel(slow.id)
        self.assertTrue(m.wait_idle(20))
        self.assertEqual(m.get(slow.id).status, Status.CANCELLED)
        self.assertEqual(m.get(fast.id).status, Status.COMPLETED)

    def test_speed_options_reach_yt_dlp(self):
        seen = {}

        def behavior(opts, url, n):
            seen.update(opts)
            return {"requested_downloads": [{"filepath": write_file(self.dest, "T [o].mp4")}]}
        m = self.manager(behavior, fragment_threads=5)
        m.enqueue([item(self.dest, "o")])
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(seen["concurrent_fragment_downloads"], 5)
        self.assertEqual(seen["http_chunk_size"], engine.HTTP_CHUNK_SIZE)
        self.assertEqual(seen["buffersize"], engine.BUFFER_SIZE)
        self.assertTrue(seen["continuedl"] and not seen["overwrites"])


class SettingsTests(unittest.TestCase):
    def test_parallel_setting_is_validated(self):
        self.assertEqual(config.Settings().parallel_downloads, 2)
        for bad in (0, 9, "3", True, None, 2.5):
            self.assertEqual(config.sanitize({"parallel_downloads": bad}).parallel_downloads, 2, bad)
        self.assertEqual(config.sanitize({"parallel_downloads": 4}).parallel_downloads, 4)
        self.assertEqual(config.sanitize({}).parallel_downloads, 2)   # settings files from older versions


class _SlowSegments(http.server.SimpleHTTPRequestHandler):
    DELAY = 0.35

    def do_GET(self):
        if self.path.endswith(".ts"):
            time.sleep(self.DELAY)
        super().do_GET()

    def log_message(self, *args):
        pass


@unittest.skipUnless(FFMPEG, "FFmpeg is not available")
class FragmentTests(unittest.TestCase):
    """A segmented (HLS) stream whose segments each take a moment, like a real CDN."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.media = os.path.join(cls.tmp.name, "media")
        os.makedirs(cls.media)
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=8:size=160x90:rate=10",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "10", "-f", "hls", "-hls_time", "1",
               "-hls_playlist_type", "vod", os.path.join(cls.media, "stream.m3u8")]
        if subprocess.run(cmd).returncode != 0:
            raise unittest.SkipTest("this FFmpeg build can't make HLS test media")
        handler = functools.partial(_SlowSegments, directory=cls.media)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def download(self, threads):
        dest = tempfile.mkdtemp(dir=self.tmp.name)
        m = DownloadManager(lambda k, p: None, ffmpeg_path=FFMPEG, min_free_bytes=1, fragment_threads=threads,
                            retry_delays=())
        t0 = time.monotonic()
        m.enqueue([DownloadItem(video_id="hls", title="hls", url=f"http://127.0.0.1:{self.port}/stream.m3u8",
                                preset_id="mp4_best", dest_dir=dest)])
        self.assertTrue(m.wait_idle(120))
        elapsed = time.monotonic() - t0
        result = m.snapshot()[0]
        self.assertEqual(result.status, Status.COMPLETED, result.error)
        self.assertGreater(os.path.getsize(result.filepath), 1000)
        return elapsed

    def test_parallel_fragments_download_faster_and_correctly(self):
        slow = self.download(1)
        fast = self.download(4)
        print(f"\n  HLS 8 segments: 1 fragment thread {slow:.1f}s, 4 threads {fast:.1f}s")
        self.assertLess(fast, slow * 0.75)

    def test_cancel_works_with_parallel_fragments(self):
        dest = tempfile.mkdtemp(dir=self.tmp.name)
        m = DownloadManager(lambda k, p: None, ffmpeg_path=FFMPEG, min_free_bytes=1, fragment_threads=4, retry_delays=())
        [it], _ = m.enqueue([DownloadItem(video_id="stream", title="hls2", url=f"http://127.0.0.1:{self.port}/stream.m3u8",
                                          preset_id="mp4_best", dest_dir=dest)])
        time.sleep(0.8)
        m.cancel(it.id)
        self.assertTrue(m.wait_idle(30))
        self.assertEqual(m.get(it.id).status, Status.CANCELLED)
        self.assertEqual([n for n in os.listdir(dest) if n.endswith((".part", ".ytdl"))], [])


if __name__ == "__main__":
    unittest.main()
