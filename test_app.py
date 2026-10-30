import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app


class CatalogTests(unittest.TestCase):
    def test_user_paths_only_and_duplicate_registry_entries(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = Path(directory)
            font = store / "sample.ttf"
            font.write_bytes(b"font")
            outside = store.parent / "outside.ttf"
            with patch.object(app, "FONT_STORE", store), patch.object(app, "font_names", return_value=("Sample", "Regular", None)):
                faces, skipped = app.build_faces([("First", font.name), ("Second", str(font)), ("Outside", str(outside))])
            self.assertEqual(len(faces), 1)
            self.assertEqual(skipped, 1)
            self.assertEqual(faces[0]["_path"], font)

    def test_oversized_font_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "large.ttf"
            with path.open("wb") as output:
                output.truncate(app.MAX_FONT_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "Font too large"):
                app.font_names(path)

    def test_bad_font_is_skipped(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = Path(directory)
            (store / "broken.ttf").write_bytes(b"bad")
            with patch.object(app, "FONT_STORE", store):
                faces, skipped = app.build_faces([("Broken", "broken.ttf")])
            self.assertEqual(faces, [])
            self.assertEqual(skipped, 1)

    def test_catalog_does_not_repeat_registry_file_from_store(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = Path(directory)
            (store / "sample.ttf").write_bytes(b"font")
            with patch.object(app, "FONT_STORE", store), patch.object(app, "registry_fonts", return_value=[("Sample", "sample.ttf")]), patch.object(app, "font_names", return_value=("Sample", "Regular", None)):
                faces, skipped = app.catalog()
            self.assertEqual((len(faces), skipped), (1, 0))

    def test_rescan_finds_new_user_font(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = Path(directory)
            with patch.object(app, "FONT_STORE", store), patch.object(app, "registry_fonts", return_value=[]), patch.object(app, "font_names", return_value=("New", "Regular", None)):
                self.assertEqual(app.catalog()[0], [])
                (store / "new.ttf").write_bytes(b"font")
                self.assertEqual(len(app.catalog()[0]), 1)

    def test_server_rejects_host_unknown_id_and_outside_font(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = Path(directory) / "Fonts"
            store.mkdir()
            outside = Path(directory) / "outside.ttf"
            outside.write_bytes(b"private")
            server = SimpleNamespace(server_port=8765, fonts={"a" * 16: outside}, refresh=lambda: None)
            with patch.object(app, "FONT_STORE", store):
                for host, route, expected in [
                    ("evil.example", "/health", 403),
                    ("127.0.0.1:8765", "/font/" + "a" * 16, 404),
                    ("127.0.0.1:8765", "/font/" + "b" * 16, 404),
                ]:
                    handler = object.__new__(app.Handler)
                    handler.server = server
                    handler.path = route
                    handler.headers = Message()
                    handler.headers["Host"] = host
                    result = []
                    handler.send_error = lambda code: result.append(code)
                    handler.send_body = lambda code, *_: result.append(code)
                    handler.do_GET()
                    self.assertEqual(result, [expected])


if __name__ == "__main__":
    unittest.main()
