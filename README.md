# Moodle Downloader

English | [简体中文](README.zh-CN.md)

Automatically downloads your (Monash) Moodle course files into tidy weekly
folders — `FIT5003/Week 01`, `Week 02`, … — and keeps them up to date all
semester. Late-released files (tutorial solutions, extra slides) are picked up
automatically on the next run. Set it to sync daily and never manually
download a lecture PDF again.

```
Your folder/
├── FIT5003/
│   ├── Week 00 ... Week 12/     <- files land in the right week
│   └── _Other/                  <- files that belong to no week
└── FIT5136/
    └── ...
```

## For everyday users (Windows, no installation)

1. Download `MoodleDownloader.exe` from
   [Releases](../../releases) and put it in any folder.
2. Double-click it and pick **setup**: it opens a browser window — log in to
   Moodle yourself (tick **"Keep me signed in"**), then choose your courses
   from a list. No course IDs, no config files.
3. Pick **Sync course files now** — done. Files appear in your chosen folder.
4. Optionally pick **Turn ON daily auto-sync** so it runs every day by itself.

Your password is typed only into the real university login page, never stored
or seen by the tool. Login cookies are kept locally in
`%LOCALAPPDATA%\moodle-downloader`.

## For developers / macOS / Linux

Requires Python 3.10+.

```bash
git clone <this repo> && cd moodle-downloader
pip install -r requirements.txt
python run.py            # interactive menu (setup, sync, ...)
python run.py sync       # or straight to a sync
```

The tool drives a real browser via Playwright. On Windows it can use your
built-in Edge, so no browser download is needed. Elsewhere, if neither Chrome
nor a Playwright browser is found, run `playwright install chromium` once.
macOS/Linux are expected to work but are not regularly tested.

## How it works

- **Login**: a real browser window opens on first run; you log in through your
  university's own SSO + MFA. Cookies (including session cookies) are saved
  locally and revived on later runs, so syncs are silent and headless until
  the session truly expires — then the window simply opens again.
- **Crawling**: every course section page is fetched, including nested
  subsections (Monash's course format nests `Week N` inside a `Learning`
  section, with `Own-time` / `Real-time` blocks inside each week — subsections
  inherit their parent's week).
- **Week matching**: section titles are matched against `Week N` / `Topic N`
  (configurable regexes in `config.yaml`).
- **Incremental**: `.manifest.json` in your download folder records every file
  already fetched. Re-runs only download new files; nothing is downloaded
  twice. Deleting a local file makes it re-download next run. If a lecturer
  replaces a file, the new version is downloaded alongside the old one.
- **Starred mode**: instead of a fixed course list, the tool can sync whatever
  courses you have starred on Moodle — handy at semester changeover.

## FAQ

**The browser window closed / I closed it by accident.** Just run sync again.

**It says "Could not log in".** Run sync again and complete the login within
10 minutes. Don't close the window — it closes itself.

**My course uses "Module 3" instead of "Week 3".** Add a pattern to
`section_patterns` in `config.yaml`, e.g. `"module\\s*0*{week}\\b"`.

**Files went to `_Other/`.** That section's title didn't match any week
pattern — same fix as above.

**Is this allowed?** It only downloads material from units you are enrolled
in, through your own login, for personal study — the same files you could
click one by one.

## Building the exe yourself

```bash
pip install pyinstaller
pyinstaller --onefile --name MoodleDownloader --collect-all playwright run.py
```

## License

MIT
