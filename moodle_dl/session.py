from __future__ import annotations

import json
import sys
import time

from playwright.sync_api import BrowserContext, Page, sync_playwright

from .config import Config

LOGIN_TIMEOUT_S = 10 * 60  # give the user 10 minutes to complete SSO + MFA


class MoodleSession:
    """A logged-in Moodle browser session backed by a persistent profile.

    The first run opens a visible browser so the user can log in through
    Okta/SSO + MFA. Cookies live in the persistent profile directory, so
    later runs reuse them headlessly until they expire.
    """

    def __init__(self, cfg: Config, headful: bool = False):
        self.cfg = cfg
        self.headful = headful
        self._pw = None
        self.ctx: BrowserContext | None = None

    def __enter__(self) -> "MoodleSession":
        self._pw = sync_playwright().start()
        self._launch(headless=not self.headful)
        if not self._ensure_logged_in():
            raise RuntimeError("Could not log in to Moodle.")
        return self

    def __exit__(self, *exc) -> None:
        if self.ctx:
            self._save_cookies()
            self.ctx.close()
        if self._pw:
            self._pw.stop()

    # -- internals ---------------------------------------------------------

    @property
    def _cookie_file(self):
        return self.cfg.session_dir / "cookies.json"

    def _save_cookies(self) -> None:
        """Persist all cookies, including session cookies that the browser
        would otherwise drop on restart (Moodle and Okta both use them)."""
        try:
            cookies = self.ctx.cookies()
            self._cookie_file.write_text(json.dumps(cookies), encoding="utf-8")
        except Exception:
            pass

    def _restore_cookies(self) -> None:
        if not self._cookie_file.exists():
            return
        try:
            cookies = json.loads(self._cookie_file.read_text(encoding="utf-8"))
            self.ctx.add_cookies(cookies)
        except Exception:
            pass

    def _launch(self, headless: bool) -> None:
        if self.ctx:
            self.ctx.close()
        self.cfg.session_dir.mkdir(parents=True, exist_ok=True)
        # Try the bundled Chromium first, then fall back to a system browser
        # (Edge ships with Windows; Chrome covers most other setups).
        last_err: Exception | None = None
        for channel in (None, "msedge", "chrome"):
            try:
                self.ctx = self._pw.chromium.launch_persistent_context(
                    str(self.cfg.session_dir),
                    channel=channel,
                    headless=headless,
                    viewport={"width": 1280, "height": 900},
                    # Headless mode advertises "HeadlessChrome" in the UA,
                    # which SSO providers may treat as a bot - use a normal UA.
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/150.0.0.0 Safari/537.36"),
                )
                self._restore_cookies()
                return
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Could not launch any browser: {last_err}")

    def _is_logged_in(self, page: Page) -> bool:
        if not page.url.startswith(self.cfg.base_url):
            return False  # bounced to Okta / SSO
        if "/login" in page.url:
            return False
        # Moodle tags the <body> with "notloggedin" for guests
        return page.locator("body.notloggedin").count() == 0

    def _wait_logged_in(self, page: Page, timeout_s: float) -> bool:
        """Poll until the page reaches a logged-in Moodle state.

        SSO providers (Okta) redirect via JavaScript, so the login state can
        flip well after the initial page load - polling is the reliable way.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                if self._is_logged_in(page):
                    return True
                page.wait_for_timeout(2000)
            except Exception:
                if page.is_closed():
                    print("Browser window was closed before login finished.",
                          file=sys.stderr)
                    return False
                time.sleep(2)
        return False

    def _ensure_logged_in(self) -> bool:
        page = self.ctx.new_page()
        dashboard = f"{self.cfg.base_url}/my/"
        page.goto(dashboard, wait_until="domcontentloaded")

        # Give silent SSO redirects a chance before involving the user.
        if self._wait_logged_in(page, 20):
            self._save_cookies()
            page.close()
            return True

        if not self.headful:
            # Session expired and we're headless: reopen visibly for login.
            print("Session expired or first run - opening a browser window "
                  "so you can log in (SSO + MFA)...", file=sys.stderr)
            self._launch(headless=False)
            page = self.ctx.new_page()
            page.goto(dashboard, wait_until="domcontentloaded")

        print("Please log in to Moodle in the browser window "
              "(waiting up to 10 minutes)...", file=sys.stderr)
        print("TIP: tick 'Keep me signed in' on the Okta page so future runs "
              "skip MFA.", file=sys.stderr)
        print("(Don't close the window - it closes by itself when the "
              "download finishes.)", file=sys.stderr)
        ok = self._wait_logged_in(page, LOGIN_TIMEOUT_S)
        if ok:
            self._save_cookies()
            if not page.is_closed():
                page.close()
        return ok

    # -- public API --------------------------------------------------------

    def get_html(self, url: str) -> str:
        resp = self.ctx.request.get(url)
        if not resp.ok:
            raise RuntimeError(f"GET {url} -> HTTP {resp.status}")
        return resp.text()

    def get_raw(self, url: str):
        """Return the APIResponse for a URL (follows redirects)."""
        return self.ctx.request.get(url, max_redirects=10)
