"""Browser screenshots and hardware-style actions; no game-specific API or state reads."""

import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class BrowserBridge:
    def __init__(self):
        self.browser = self.playwright = self.server = None
        self.keys, self.buttons = set(), set()
        self.pointer = self.virtual_pointer = (0, 0)
        self.elapsed_ms = self.captures = 0

    def open(self, params):
        url = params.get("url")
        if not url:
            root = Path(params["root"]).resolve()
            if not (root / "index.html").is_file():
                raise ValueError("local game needs index.html; use a URL for a dev server")
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
            Thread(target=self.server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{self.server.server_port}/"
        self.directory = Path(params["directory"]).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        # Playwright logs the actual executable and launch arguments to stderr.
        os.environ["DEBUG"] = ",".join(filter(None, [os.environ.get("DEBUG"), "pw:browser"]))
        self.playwright = sync_playwright().start()
        gpu_args = ["--enable-gpu", "--ignore-gpu-blocklist"]
        if sys.platform == "darwin":
            gpu_args.append("--use-angle=metal")
        self.browser = self.playwright.chromium.launch(
            executable_path=os.environ.get("CHROME_PATH"), args=gpu_args,
            ignore_default_args=["--enable-unsafe-swiftshader"])
        print(f"Browser version: {self.browser.version}", file=sys.stderr, flush=True)
        self.page = self.browser.new_page(viewport={"width": params.get("width", 960), "height": params.get("height", 960)})
        self.page.on("console", lambda message: print(
            f"Browser console [{message.type}]: {message.text}", file=sys.stderr, flush=True))
        renderer = self.page.evaluate("""() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
            if (!gl) return null;
            const info = gl.getExtension('WEBGL_debug_renderer_info');
            return info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
        }""")
        if not renderer or any(name in renderer.lower() for name in ("swiftshader", "software", "llvmpipe", "subzero")):
            raise RuntimeError(f"Hardware GPU required; WebGL renderer: {renderer}")
        print(f"GPU renderer: {renderer}", file=sys.stderr)
        self.page.on("pageerror", lambda error: print(error, file=sys.stderr))
        self.page.clock.install(time=0)
        self.page.clock.pause_at(1)  # pause on the blank page, before any game timers exist
        self.page.goto(url, wait_until="load", timeout=30000)
        self.page.clock.run_for(16)  # allow an initial animation frame before the first observation
        return {"url": url}

    def step(self, params):
        actions = params["actions"]
        action_interval_ms = params["action_interval_ms"]
        if type(action_interval_ms) is not int or action_interval_ms < 1:
            raise ValueError("action_interval_ms must be positive integer milliseconds")
        if not actions:
            raise ValueError("active steps require at least one action")
        for command in actions:
            keys, mouse = set(command["keys"]), command["mouse"]
            relative = "dx" in mouse or "dy" in mouse
            absolute = "x" in mouse or "y" in mouse
            pointer = self.virtual_pointer
            if relative or absolute:
                locked = self.page.evaluate("document.pointerLockElement !== null")
                # Ignore coordinates for the inactive mode as lock state changes mid-plan.
                relative = relative and locked
                absolute = absolute and not locked
                if relative:
                    pointer = (self.virtual_pointer[0] + mouse.get("dx", 0),
                               self.virtual_pointer[1] + mouse.get("dy", 0))
                elif absolute:
                    pointer = (mouse.get("x", self.pointer[0]), mouse.get("y", self.pointer[1]))
                    width, height = self.page.viewport_size["width"], self.page.viewport_size["height"]
                    if not (0 <= pointer[0] < width and 0 <= pointer[1] < height):
                        raise ValueError(f"absolute pointer bounds: 0 <= x < {width}, 0 <= y < {height}")
            for key in sorted(self.keys - keys):
                self.page.keyboard.up(key)
            for key in command["keys"]:
                if key not in self.keys:
                    self.page.keyboard.down(key)
            self.keys = keys
            if pointer != self.virtual_pointer or absolute:
                self.page.mouse.move(*pointer)
                self.virtual_pointer = pointer
                if absolute:
                    self.pointer = pointer  # absolute position stays fixed while pointer-locked
            buttons = set(mouse["buttons"])
            for button in sorted(self.buttons - buttons):
                self.page.mouse.up(button=button)
            for button in sorted(buttons - self.buttons):
                self.page.mouse.down(button=button)
            self.buttons = buttons
            self.page.clock.run_for(action_interval_ms)
            self.elapsed_ms += action_interval_ms
        return {}

    def render(self, params):
        path = self.directory / f"f{self.captures:04d}.jpg"
        self.page.screenshot(path=str(path), type="jpeg", quality=70, timeout=15000)
        self.captures += 1
        return {"frame": str(path), "elapsed_ms": self.elapsed_ms,
                "pointer_locked": self.page.evaluate("document.pointerLockElement !== null")}

    def close(self, params=None):
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        return {}


if __name__ == "__main__":
    bridge = BrowserBridge()
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                if request["method"] not in ("open", "step", "render", "close"):
                    raise ValueError("unknown browser method")
                reply = {"id": request["id"], "result": getattr(bridge, request["method"])(request["params"])}
            except Exception as error:
                reply = {"id": request["id"], "error": str(error)}
            print(json.dumps(reply), flush=True)
    finally:
        bridge.close()
