import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
import yt_dlp
from kdownloader import engine, system
from kdownloader.engine import DownloadItem, DownloadManager, EntryInfo, Status


def make_factory(behavior):
    """A stand-in for yt_dlp.YoutubeDL driven by ``behavior(opts, url)``."""
    class FakeYDL:
        calls = 0

        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=True):
            FakeYDL.calls += 1
            return behavior(self.opts, url, FakeYDL.calls)
    return FakeYDL


def write_file(dest, name, data=b"x" * 2048):
    path = os.path.join(dest, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def good_behavior(dest, vid="vid1"):
    def behavior(opts, url, call_no):
        hook = opts["progress_hooks"][0]
        hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000, "speed": 100.0, "eta": 5,
              "info_dict": {"requested_formats": [{}, {}]}})
        time.sleep(0.25)
        hook({"status": "downloading", "downloaded_bytes": 1000, "total_bytes": 1000, "speed": 100.0, "eta": 0})
        hook({"status": "finished"})
        time.sleep(0.25)
        hook({"status": "downloading", "downloaded_bytes": 800, "total_bytes": 1000, "speed": 50.0, "eta": 1})
        hook({"status": "finished"})
        opts["postprocessor_hooks"][0]({"status": "started"})
        path = write_file(dest, f"Title [{vid}].mp4")
        return {"requested_downloads": [{"filepath": path}]}
    return behavior


def item(dest, vid="vid1", **kw):
    return DownloadItem(video_id=vid, title=f"Title {vid}", url=f"http://x/{vid}", preset_id="mp4_720",
                        dest_dir=dest, **kw)


class Collector:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def __call__(self, kind, payload):
        with self.lock:
            self.events.append((kind, payload))

    def kinds(self):
        with self.lock:
            return [k for k, _ in self.events]

    def finished(self):
        with self.lock:
            return [p for k, p in self.events if k == "finished"]


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = os.path.join(self.tmp.name, "out")
        self.col = Collector()

    def tearDown(self):
        self.tmp.cleanup()

    def manager(self, behavior, **kw):
        kw.setdefault("retry_delays", (0.0, 0.0))
        kw.setdefault("min_free_bytes", 1)
        return DownloadManager(self.col, ffmpeg_path="/fake/ffmpeg", ydl_factory=make_factory(behavior), **kw)

    def test_successful_download(self):
        m = self.manager(good_behavior(self.dest))
        accepted, dup = m.enqueue([item(self.dest)])
        self.assertEqual((len(accepted), dup), (1, 0))
        self.assertTrue(m.wait_idle(10))
        [done] = self.col.finished()
        self.assertEqual(done.status, Status.COMPLETED)
        self.assertTrue(done.filepath.endswith("Title [vid1].mp4"))
        self.assertEqual(done.progress, 1.0)
        self.assertEqual(done.size, 2048)
        kinds = self.col.kinds()
        self.assertEqual(kinds[0], "added"); self.assertEqual(kinds[-1], "idle")
        progress = [p for k, p in self.col.events if k == "progress"]
        self.assertTrue(any(p.status == Status.PROCESSING for p in progress))
        values = [p.progress for p in progress]
        self.assertEqual(values, sorted(values), "progress must never go backwards")
        self.assertFalse(m.is_active())

    def test_existing_file_is_not_overwritten(self):
        os.makedirs(self.dest)
        existing = write_file(self.dest, "Old title [vid1].mp4", b"precious")
        m = self.manager(lambda *a: self.fail("must not download"))
        m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(self.col.finished()[0].status, Status.SKIPPED)
        self.assertEqual(Path(existing).read_bytes(), b"precious")

    def test_partial_files_do_not_count_as_existing(self):
        os.makedirs(self.dest)
        write_file(self.dest, "Title [vid1].mp4.part")
        self.assertIsNone(system.find_existing(self.dest, "vid1"))

    def test_private_video_fails_without_retry(self):
        def behavior(opts, url, n):
            raise yt_dlp.utils.DownloadError("ERROR: [youtube] vid1: Private video. Sign in if you've been granted access")
        m = self.manager(behavior)
        m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        [done] = self.col.finished()
        self.assertEqual((done.status, done.error_code), (Status.FAILED, "private"))
        self.assertIn("private", done.error.lower())
        self.assertEqual(make_factory(behavior).calls, 0)  # (fresh class) sanity

    def test_network_errors_are_retried_then_succeed(self):
        inner = good_behavior(self.dest)

        def behavior(opts, url, n):
            if n < 3:
                raise yt_dlp.utils.DownloadError("ERROR: Unable to download webpage: timed out")
            return inner(opts, url, n)
        m = self.manager(behavior)
        m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(self.col.finished()[0].status, Status.COMPLETED)

    def test_network_failure_then_manual_retry(self):
        state = {"fail": True}
        inner = good_behavior(self.dest)

        def behavior(opts, url, n):
            if state["fail"]:
                raise yt_dlp.utils.DownloadError("ERROR: Unable to download: Connection reset by peer")
            return inner(opts, url, n)
        m = self.manager(behavior)
        [it], _ = m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        failed = m.get(it.id)
        self.assertEqual((failed.status, failed.error_code, failed.retryable), (Status.FAILED, "network", True))
        state["fail"] = False
        self.assertEqual(m.retry([it.id]), 1)
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(m.get(it.id).status, Status.COMPLETED)
        self.assertEqual(m.retry(), 0)  # nothing left to retry

    def test_cancel_running_download_cleans_partials(self):
        started = threading.Event()
        os.makedirs(self.dest, exist_ok=True)

        def behavior(opts, url, n):
            write_file(self.dest, "Title [vid1].mp4.part")
            hook = opts["progress_hooks"][0]
            for i in range(200):
                started.set()
                hook({"status": "downloading", "downloaded_bytes": i, "total_bytes": 1000})
                time.sleep(0.02)
            self.fail("cancel was ignored")
        m = self.manager(behavior)
        [it], _ = m.enqueue([item(self.dest)])
        self.assertTrue(started.wait(5))
        m.cancel(it.id)
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(m.get(it.id).status, Status.CANCELLED)
        self.assertEqual([n for n in os.listdir(self.dest) if n.endswith(".part")], [])

    def test_stop_all_cancels_queue_and_current(self):
        started = threading.Event()

        def behavior(opts, url, n):
            hook = opts["progress_hooks"][0]
            while True:
                started.set()
                hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})
                time.sleep(0.02)
        m = self.manager(behavior)
        m.enqueue([item(self.dest, "a"), item(self.dest, "b"), item(self.dest, "c")])
        self.assertTrue(started.wait(5))
        m.stop_all()
        self.assertTrue(m.wait_idle(10))
        self.assertEqual({i.status for i in m.snapshot()}, {Status.CANCELLED})
        self.assertEqual(self.col.kinds()[-1], "idle")

    def test_duplicates_are_ignored(self):
        started = threading.Event()
        release = threading.Event()

        def behavior(opts, url, n):
            started.set(); release.wait(5)
            return good_behavior(self.dest)(opts, url, n)
        m = self.manager(behavior)
        m.enqueue([item(self.dest)])
        started.wait(5)
        accepted, dup = m.enqueue([item(self.dest)])
        self.assertEqual((len(accepted), dup), (0, 1))
        release.set(); self.assertTrue(m.wait_idle(10))

    def test_unusable_folder_fails_clearly(self):
        blocker = write_file(self.tmp.name, "afile")
        m = self.manager(lambda *a: self.fail("no download"))
        m.enqueue([item(os.path.join(blocker, "sub"))])
        self.assertTrue(m.wait_idle(10))
        done = self.col.finished()[0]
        self.assertEqual((done.status, done.error_code), (Status.FAILED, "folder"))

    def test_low_disk_space_is_reported(self):
        m = self.manager(lambda *a: self.fail("no download"), min_free_bytes=1 << 62)
        m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(self.col.finished()[0].error_code, "disk_full")

    def test_clear_finished_and_remove(self):
        m = self.manager(good_behavior(self.dest))
        m.enqueue([item(self.dest)])
        self.assertTrue(m.wait_idle(10))
        self.assertEqual(len(m.snapshot()), 1)
        m.clear_finished()
        self.assertEqual(m.snapshot(), [])
        self.assertIn("removed", self.col.kinds())


class SummaryTests(unittest.TestCase):
    def test_summarize(self):
        a = DownloadItem("1", "a", "u", "mp4_720", "d", status=Status.COMPLETED, started_at=1, finished_at=11)
        b = DownloadItem("2", "b", "u", "mp4_720", "d", status=Status.FAILED)
        c = DownloadItem("3", "c", "u", "mp4_720", "d", status=Status.DOWNLOADING, progress=0.5, speed=100.0, eta=5)
        d = DownloadItem("4", "d", "u", "mp4_720", "d", status=Status.QUEUED)
        s = engine.summarize([a, b, c, d])
        self.assertEqual((s["total"], s["completed"], s["failed"], s["active"], s["queued"]), (4, 1, 1, 1, 1))
        self.assertAlmostEqual(s["progress"], (2 + 0.5) / 4)
        self.assertEqual(s["speed"], 100.0)
        self.assertEqual(s["eta"], 5 + 10)
        self.assertEqual(engine.summarize([])["progress"], 0.0)


class FetchTests(unittest.TestCase):
    def test_fetch_playlist_filters_unavailable_and_duplicates(self):
        info = {"title": "My list", "uploader": "Me", "entries": [
            {"id": "a", "title": "One", "url": "https://www.youtube.com/watch?v=a", "duration": 61},
            {"id": "b", "title": "[Private video]", "url": "https://www.youtube.com/watch?v=b"},
            None,
            {"id": "a", "title": "One again", "url": "https://www.youtube.com/watch?v=a"},
            {"id": "c", "title": "Three", "url": "https://www.youtube.com/watch?v=c", "duration": None},
        ]}
        pl = engine.fetch_playlist("https://x", make_factory(lambda *a: info))
        self.assertEqual((pl.title, len(pl.entries), pl.unavailable), ("My list", 2, 2))
        self.assertEqual(pl.entries[0].duration, 61)
        self.assertTrue(pl.thumbnail_url.endswith("/a/mqdefault.jpg"))

    def test_fetch_playlist_errors(self):
        def raises(opts, url, n):
            raise yt_dlp.utils.DownloadError("ERROR: [youtube:tab] x: This playlist is private")
        with self.assertRaises(engine.FetchError) as ctx:
            engine.fetch_playlist("https://x", make_factory(raises))
        self.assertEqual(ctx.exception.friendly.code, "private")
        with self.assertRaises(engine.FetchError) as ctx:
            engine.fetch_playlist("https://x", make_factory(lambda *a: {"id": "v", "title": "single"}))
        self.assertEqual(ctx.exception.friendly.code, "not_playlist")
        with self.assertRaises(engine.FetchError) as ctx:
            engine.fetch_playlist("https://x", make_factory(lambda *a: {"title": "t", "entries": []}))
        self.assertEqual(ctx.exception.friendly.code, "empty")

    def test_fetch_video(self):
        v = engine.fetch_video("https://x", make_factory(lambda *a: {
            "id": "abc", "title": "Hello", "duration": 9, "webpage_url": "https://x/abc", "thumbnail": "https://t/i.jpg"}))
        self.assertEqual((v.video_id, v.title, v.duration, v.url), ("abc", "Hello", 9, "https://x/abc"))
        with self.assertRaises(engine.FetchError):
            engine.fetch_video("https://x", make_factory(lambda *a: {"id": "l", "is_live": True, "title": "t"}))

    def test_thumbnail_only_https(self):
        self.assertIsNone(engine.fetch_thumbnail("http://example.com/a.jpg"))
        self.assertIsNone(engine.fetch_thumbnail(None))


if __name__ == "__main__":
    unittest.main()
