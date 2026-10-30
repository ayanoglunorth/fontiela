"""One-click, loopback-only Windows font catalog."""

import hashlib
import json
import os
import re
import struct
import subprocess
import urllib.request
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FONT_STORE = Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Windows/Fonts"
MAX_FONT_BYTES = 32 * 1024 * 1024
FONT_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
HEALTH = b"fontiela/1/" + hashlib.sha256(str(ROOT).casefold().encode("utf-8") + Path(__file__).read_bytes()).hexdigest()[:16].encode()


def registry_fonts(hive):
    try:
        with winreg.OpenKey(hive, FONT_KEY) as key:
            return [winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1])]
    except FileNotFoundError:
        return []


def font_path(value):
    path = Path(value)
    path = (path if path.is_absolute() else FONT_STORE / path).resolve()
    if not path.is_relative_to(FONT_STORE.resolve()):
        raise ValueError("Font outside user store")
    return path


def font_names(path):
    if path.stat().st_size > MAX_FONT_BYTES:
        raise ValueError("Font too large")
    data = path.read_bytes()
    offset = struct.unpack_from(">I", data, 12)[0] if data[:4] == b"ttcf" else 0
    if data[offset:offset + 4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise ValueError("Unsupported font format")
    count = struct.unpack_from(">H", data, offset + 4)[0]
    tables = {}
    for i in range(count):
        tag, _, start, length = struct.unpack_from(">4sIII", data, offset + 12 + 16 * i)
        if start + length > len(data):
            raise ValueError("Invalid font table")
        tables[tag] = (start, length)
    start, length = tables[b"name"]
    name_data = data[start:start + length]
    record_count, storage = struct.unpack_from(">HH", name_data, 2)
    names = {}
    for i in range(record_count):
        platform, _, language, name_id, size, pos = struct.unpack_from(">HHHHHH", name_data, 6 + 12 * i)
        if name_id not in (1, 2, 16, 17) or platform not in (0, 3) or storage + pos + size > len(name_data):
            continue
        try:
            value = name_data[storage + pos:storage + pos + size].decode("utf-16-be").strip()
        except UnicodeError:
            continue
        if value and (name_id not in names or language == 0x409):
            names[name_id] = value
    family = names.get(16) or names.get(1)
    if not family:
        raise ValueError("Font family name missing")
    style = names.get(17) or names.get(2) or "Regular"
    weight = None
    if b"fvar" in tables:
        start, _ = tables[b"fvar"]
        axes_offset, _, axes_count, axes_size = struct.unpack_from(">HHHH", data, start + 4)
        for i in range(axes_count):
            axis = start + axes_offset + i * axes_size
            tag, minimum, default, maximum = struct.unpack_from(">4siii", data, axis)
            if tag == b"wght":
                weight = [round(v / 65536) for v in (minimum, default, maximum)]
                break
    return family, style, weight


def build_faces(user_entries):
    faces = []
    skipped = 0
    seen = set()
    for _, value in user_entries:
        try:
            path = font_path(value)
            if path.suffix.lower() not in (".ttf", ".otf", ".ttc") or path in seen:
                continue
            family, style, weight = font_names(path)
        except (OSError, ValueError, KeyError, struct.error, IndexError):
            skipped += 1
            continue
        seen.add(path)
        face_id = hashlib.sha256(str(path).casefold().encode("utf-8")).hexdigest()[:16]
        faces.append({"id": face_id, "family": family, "style": style, "weight": weight,
                      "filename": path.name, "source": "user", "_path": path})
    return faces, skipped


def catalog():
    faces, skipped = build_faces(registry_fonts(winreg.HKEY_CURRENT_USER))
    known_paths = {str(face["_path"]).casefold() for face in faces}
    known_styles = {(face["family"].casefold(), face["style"].casefold()) for face in faces}
    static_families = {face["family"].casefold() for face in faces if face["weight"] is None}
    try:
        paths = sorted(FONT_STORE.iterdir(), key=lambda path: ("variablefont" in path.name.casefold(), path.name.casefold()))
    except OSError:
        return faces, skipped
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            continue
        try:
            path = font_path(str(path))
            if str(path).casefold() in known_paths:
                continue
            family, style, weight = font_names(path)
        except (OSError, ValueError, KeyError, struct.error, IndexError):
            skipped += 1
            continue
        key = family.casefold(), style.casefold()
        if key in known_styles or (weight is not None and family.casefold() in static_families):
            continue
        face_id = hashlib.sha256(f"user-store\0{path}".encode("utf-8")).hexdigest()[:16]
        faces.append({"id": face_id, "family": family, "style": style, "weight": weight,
                      "filename": path.name, "source": "user", "_path": path})
        known_styles.add(key)
        if weight is None:
            static_families.add(family.casefold())
    return faces, skipped


class CatalogServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def refresh(self):
        faces, skipped = catalog()
        self.fonts = {face["id"]: face["_path"] for face in faces}
        self.installed_families = {face["family"] for face in faces}
        return [{key: value for key, value in face.items() if key != "_path"} for face in faces], skipped


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_error(403)
            return
        if self.path == "/health":
            self.send_body(200, HEALTH, "text/plain; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self.send_body(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/fonts":
            faces, skipped = self.server.refresh()
            self.send_body(200, json.dumps({"faces": faces, "skipped": skipped, "installedFamilies": sorted(self.server.installed_families)}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif re.fullmatch(r"/font/[0-9a-f]{16}", self.path):
            face_id = self.path.rsplit("/", 1)[1]
            if not hasattr(self.server, "fonts") or face_id not in self.server.fonts:
                self.server.refresh()
            path = self.server.fonts.get(face_id)
            try:
                path = font_path(str(path)) if path else None
                if not path or not path.is_file() or path.stat().st_size > MAX_FONT_BYTES:
                    raise ValueError("Font unavailable")
                body = path.read_bytes()
            except (OSError, ValueError):
                self.send_error(404)
                return
            mime = "font/otf" if path.suffix.lower() == ".otf" else "font/ttf"
            self.send_body(200, body, mime)
        elif self.path == "/icon.svg":
            self.send_body(200, (ROOT / "fontiela.svg").read_bytes(), "image/svg+xml")
        elif self.path == "/favicon.ico":
            self.send_body(200, (ROOT / "fontiela.ico").read_bytes(), "image/x-icon")
        else:
            self.send_error(404)

    def send_body(self, status, body, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def open_chrome(url):
    choices = [Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
               Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"]
    browser = next((path for path in choices if path.is_file()), None)
    if not browser:
        raise RuntimeError("Chrome veya Edge bulunamadı")
    subprocess.Popen([str(browser), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    for port in range(8765, 8776):
        url = f"http://127.0.0.1:{port}/"
        try:
            with urllib.request.urlopen(url + "health", timeout=0.25) as response:
                if response.read() == HEALTH:
                    open_chrome(url)
                    return
        except (OSError, TimeoutError):
            pass
        try:
            server = CatalogServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
        open_chrome(url)
        server.serve_forever()
        return
    raise RuntimeError("Yerel katalog için boş port bulunamadı")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(exc), "fontiela hatası", 0x10)
