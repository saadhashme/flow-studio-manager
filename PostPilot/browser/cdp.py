"""Synchronous CDP (Chrome DevTools Protocol) client for PostPilot v1.

Built on the `websocket-client` pip package (`import websocket`), this module
provides a small blocking CDP client used by the uploader modules to drive the
Chrome windows managed by :class:`ChromeHost`.

Design:
  * One background reader thread receives every message from the websocket and
    dispatches it: method-call responses are matched to the waiting caller by
    their numeric ``id`` via a per-request ``threading.Event``; CDP *events*
    (messages without an ``id``) are handed to registered event subscribers.
  * ``call(method, params, timeout)`` raises :class:`CDPTimeout` when no
    response arrives in time, and :class:`CDPError` when the peer returns an
    error object.

Proxy authentication (no native Chrome support for inline proxy creds):
  * Chrome does not accept ``user:pass@`` inside ``--proxy-server``. Instead,
    we enable the CDP ``Fetch`` domain with ``handleAuthRequests=True`` and
    intercept every ``Fetch.authRequired`` event. When the challenge comes
    from the *proxy* (``authChallenge.source == "Proxy"``), we answer with
    ``Fetch.continueWithAuth`` carrying ``{"response": "ProvideCredentials",
    "username": ..., "password": ...}``. Challenges from any other source
    (e.g. a website's own HTTP auth dialog) are passed through with the
    ``"Default"`` response so site behaviour is unchanged.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request

import websocket


class CDPError(Exception):
    """Base class for all CDP client errors."""


class CDPTimeout(CDPError):
    """Raised when a CDP method call does not receive a response in time."""


class CDPClient:
    """Blocking CDP client over the remote-debugging port of a Chrome instance.

    Usage::

        client = CDPClient(port=9331)
        client.connect()
        try:
            client.navigate("https://example.com")
            client.wait_selector("input[name=q]")
        finally:
            client.close()
    """

    def __init__(self, port: int, timeout: float = 30):
        self.port = port
        self.timeout = timeout
        self._ws: websocket.WebSocket | None = None
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()          # guards _next_id and _pending
        self._next_id = 0
        self._pending: dict[int, dict] = {}    # id -> {"event": Event, "result"/"error"}
        self._subscribers: dict[str, list] = {}  # event name -> [callbacks]
        self._running = False
        # Proxy auth state (set via set_proxy_auth).
        self._proxy_username: str | None = None
        self._proxy_password: str | None = None
        self._fetch_enabled = False

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #
    def connect(self) -> None:
        """Open the websocket to a page target.

        Fetches ``http://127.0.0.1:<port>/json`` (the DevTools target list),
        picks the first *page* target, and connects to its
        ``webSocketDebuggerUrl``. Raises :class:`CDPError` on any failure.

        After connecting, enables the ``Page``, ``Runtime`` and ``DOM``
        domains so helpers can navigate, evaluate JS and query the DOM.
        """
        targets_url = f"http://127.0.0.1:{self.port}/json"
        try:
            with urllib.request.urlopen(targets_url, timeout=10) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise CDPError(f"Cannot reach DevTools target list at {targets_url}: {exc}") from exc

        ws_url = None
        for target in targets:
            if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                ws_url = target["webSocketDebuggerUrl"]
                break
        if ws_url is None:
            raise CDPError(f"No page target with webSocketDebuggerUrl found at {targets_url}")

        try:
            self._ws = websocket.create_connection(ws_url, timeout=self.timeout)
        except Exception as exc:
            raise CDPError(f"Cannot open websocket to {ws_url}: {exc}") from exc

        # Install the proxy-auth handler BEFORE the reader starts so no
        # challenge can be missed.
        self.on("Fetch.authRequired", self._on_fetch_auth_required)

        self._running = True
        self._reader = threading.Thread(target=self._read_loop, name="cdp-reader", daemon=True)
        self._reader.start()

        # Enable the core domains the helpers rely on.
        try:
            self.call("Page.enable", timeout=self.timeout)
            self.call("Runtime.enable", timeout=self.timeout)
            self.call("DOM.enable", timeout=self.timeout)
        except Exception as exc:
            self.close()
            raise CDPError(f"Failed to enable core CDP domains: {exc}") from exc

        # If credentials were queued before connect (or after, via
        # set_proxy_auth which calls _ensure_fetch_enabled itself), arm Fetch.
        if self._proxy_username is not None:
            self._ensure_fetch_enabled()

    def close(self) -> None:
        """Stop the reader thread and close the websocket."""
        self._running = False
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        reader, self._reader = self._reader, None
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Low-level protocol plumbing
    # ------------------------------------------------------------------ #
    def _read_loop(self) -> None:
        """Background thread: dispatch responses by id, events to subscribers."""
        while self._running:
            try:
                raw = self._ws.recv() if self._ws else None
            except Exception:
                break  # socket closed / network error -> exit the loop
            if not raw:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if "id" in msg:
                # This is a response to a call(); wake the waiter.
                with self._lock:
                    slot = self._pending.pop(msg["id"], None)
                if slot is not None:
                    if "error" in msg:
                        slot["error"] = msg["error"]
                    else:
                        slot["result"] = msg.get("result")
                    slot["event"].set()
            else:
                # This is an event (no id); notify subscribers.
                method = msg.get("method")
                params = msg.get("params", {})
                for cb in list(self._subscribers.get(method, [])):
                    try:
                        cb(params)
                    except Exception:
                        pass  # never let a handler kill the reader thread

    def on(self, event_name: str, callback) -> None:
        """Register ``callback(params)`` for a CDP event such as
        ``Fetch.authRequired``."""
        self._subscribers.setdefault(event_name, []).append(callback)

    def call(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        """Send one CDP method call and block for its response.

        Returns the ``result`` object. Raises :class:`CDPTimeout` when the
        response does not arrive within ``timeout`` seconds, and
        :class:`CDPError` when the peer returns an error.
        """
        if self._ws is None:
            raise CDPError("CDPClient is not connected (call connect() first)")
        if timeout is None:
            timeout = self.timeout

        with self._lock:
            self._next_id += 1
            req_id = self._next_id
            slot = {"event": threading.Event(), "result": None, "error": None}
            self._pending[req_id] = slot

        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params
        try:
            self._ws.send(json.dumps(payload))
        except Exception as exc:
            with self._lock:
                self._pending.pop(req_id, None)
            raise CDPError(f"Failed to send {method}: {exc}") from exc

        if not slot["event"].wait(timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise CDPTimeout(f"CDP call timed out after {timeout}s: {method}")

        if slot["error"] is not None:
            raise CDPError(f"CDP error for {method}: {slot['error']}")
        return slot["result"] or {}

    # ------------------------------------------------------------------ #
    # Proxy authentication via the Fetch domain
    # ------------------------------------------------------------------ #
    def set_proxy_auth(self, username: str, password: str) -> None:
        """Arm automatic proxy authentication.

        Enables the Fetch domain with ``handleAuthRequests=True`` (patterns
        ``*``) and answers every proxy-origin auth challenge with the supplied
        credentials. Safe to call before or after :meth:`connect`; if the
        client is already connected, Fetch is enabled immediately, otherwise
        it is armed during connect().
        """
        self._proxy_username = username
        self._proxy_password = password
        if self._ws is not None:
            self._ensure_fetch_enabled()

    def _ensure_fetch_enabled(self) -> None:
        if not self._fetch_enabled:
            self.call(
                "Fetch.enable",
                {"handleAuthRequests": True, "patterns": [{"urlPattern": "*"}]},
                timeout=self.timeout,
            )
            self._fetch_enabled = True

    def _on_fetch_auth_required(self, params: dict) -> None:
        """Answer proxy auth challenges, pass through everything else."""
        request_id = params.get("requestId")
        if not request_id:
            return
        challenge = params.get("authChallenge", {}) or {}
        if challenge.get("source") == "Proxy" and self._proxy_username is not None:
            auth = {
                "response": "ProvideCredentials",
                "username": self._proxy_username,
                "password": self._proxy_password or "",
            }
        else:
            # Not a proxy challenge (e.g. a site's own login prompt) -> let
            # the browser handle it as usual.
            auth = {"response": "Default"}
        try:
            self.call("Fetch.continueWithAuth", {"requestId": request_id, "authChallengeResponse": auth},
                      timeout=self.timeout)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Page helpers
    # ------------------------------------------------------------------ #
    def navigate(self, url: str) -> None:
        """Navigate the page to ``url`` (fires-and-forgets the load event)."""
        self.call("Page.navigate", {"url": url})

    def reload(self) -> None:
        """Reload the current page."""
        self.call("Page.reload", {})

    def evaluate(self, js: str):
        """Evaluate JS in the page; return the parsed result value (or None)."""
        res = self.call("Runtime.evaluate", {"expression": js, "returnByValue": True})
        if not res:
            return None
        result = res.get("result", {})
        if result.get("subtype") == "error":
            raise CDPError(f"JS evaluation error: {result.get('description')}")
        return result.get("value")

    def wait_selector(self, css: str, timeout: float = 30) -> bool:
        """Poll until ``document.querySelector(css)`` matches (or timeout)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.evaluate(f"!!document.querySelector({json.dumps(css)})"):
                    return True
            except CDPError:
                pass
            time.sleep(0.5)
        return False

    def query_exists(self, css: str) -> bool:
        """Single check: does ``document.querySelector(css)`` match?"""
        try:
            return bool(self.evaluate(f"!!document.querySelector({json.dumps(css)})"))
        except CDPError:
            return False

    def click(self, css: str, timeout: float = 30) -> bool:
        """Wait for the selector, scroll it into view, and click it via JS."""
        if not self.wait_selector(css, timeout):
            return False
        try:
            self.evaluate(
                "(function(sel){"
                "  var el = document.querySelector(sel);"
                "  if (!el) return false;"
                "  el.scrollIntoView({block: 'center'});"
                "  el.click();"
                "  return true;"
                "})(" + json.dumps(css) + ")"
            )
            return True
        except CDPError:
            return False

    def type_text(self, css: str, text: str, clear_first: bool = True, timeout: float = 30) -> bool:
        """Wait for the selector, optionally clear it, focus it and type text.

        Uses real key events via ``document.execCommand('insertText')`` so
        framework listeners (React/Vue) pick the change up.
        """
        if not self.wait_selector(css, timeout):
            return False
        try:
            if clear_first:
                self.evaluate(
                    "(function(sel){"
                    "  var el = document.querySelector(sel);"
                    "  if (!el) return false;"
                    "  el.focus();"
                    "  if ('value' in el) { el.value = ''; }"
                    "  else { el.textContent = ''; }"
                    "  el.dispatchEvent(new Event('input', {bubbles: true}));"
                    "  return true;"
                    "})(" + json.dumps(css) + ")"
                )
            ok = self.evaluate(
                "(function(sel, txt){"
                "  var el = document.querySelector(sel);"
                "  if (!el) return false;"
                "  el.focus();"
                "  if (document.execCommand('insertText', false, txt)) return true;"
                "  if ('value' in el) {"
                "    el.value = (el.value || '') + txt;"
                "    el.dispatchEvent(new Event('input', {bubbles: true}));"
                "    el.dispatchEvent(new Event('change', {bubbles: true}));"
                "    return true;"
                "  }"
                "  el.textContent = txt;"
                "  el.dispatchEvent(new Event('input', {bubbles: true}));"
                "  return true;"
                "})(" + json.dumps(css) + ", " + json.dumps(text) + ")"
            )
            return bool(ok)
        except CDPError:
            return False

    def set_file_input(self, css: str, file_path: str, timeout: float = 30) -> bool:
        """Set files on an ``<input type=file>`` via ``DOM.setFileInputFiles``."""
        if not self.wait_selector(css, timeout):
            return False
        try:
            res = self.call("DOM.getDocument", {"depth": 0}, timeout=timeout)
            root = (res or {}).get("root", {})
            doc_id = root.get("nodeId")
            node = self.call("DOM.querySelector", {"nodeId": doc_id, "selector": css}, timeout=timeout)
            backend_id = node.get("backendNodeId")
            if not backend_id:
                return False
            self.call("DOM.setFileInputFiles", {"files": [file_path], "backendNodeId": backend_id},
                      timeout=timeout)
            return True
        except (CDPError, CDPTimeout):
            return False

    def wait_url_contains(self, substr: str, timeout: float = 90) -> bool:
        """Poll until the current URL contains ``substr`` (or timeout)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if substr in (self.current_url() or ""):
                    return True
            except CDPError:
                pass
            time.sleep(1.0)
        return False

    def wait_text_present(self, text: str, timeout: float = 90) -> bool:
        """Poll ``document.body.innerText`` until ``text`` appears (or timeout)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                body = self.evaluate("document.body ? document.body.innerText : ''") or ""
                if text in body:
                    return True
            except CDPError:
                pass
            time.sleep(1.0)
        return False

    def current_url(self) -> str:
        """Return the current page URL (``window.location.href``)."""
        try:
            return self.evaluate("window.location.href") or ""
        except CDPError:
            return ""

    def page_title(self) -> str:
        """Return the current page title."""
        try:
            return self.evaluate("document.title") or ""
        except CDPError:
            return ""

    def screenshot(self, path: str) -> None:
        """Capture the page as PNG and write it to ``path``."""
        res = self.call("Page.captureScreenshot", {"format": "png"})
        data = (res or {}).get("data")
        if not data:
            raise CDPError("Page.captureScreenshot returned no image data")
        import base64

        with open(path, "wb") as fh:
            fh.write(base64.b64decode(data))

    def sleep(self, seconds: float) -> None:
        """Simple blocking sleep helper (kept here so uploaders don't import time)."""
        time.sleep(seconds)
