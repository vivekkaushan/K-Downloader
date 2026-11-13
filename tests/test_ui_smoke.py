"""Builds the real window and visits every page. Skipped when no display is available."""
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401


def _display_ok() -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(_display_ok(), "no display available")
class UiSmokeTest(unittest.TestCase):
    def test_every_page_opens_and_window_closes(self):
        os.environ["KDOWNLOADER_HOME"] = tempfile.mkdtemp()
        from kdownloader.ui.app import KDownloaderApp, NAV
        app = KDownloaderApp(show_welcome=False)
        try:
            for key, _, _ in NAV:
                app.show_page(key)
                app.update()
                self.assertEqual(app.current, key)
        finally:
            app._on_close()


if __name__ == "__main__":
    unittest.main()
