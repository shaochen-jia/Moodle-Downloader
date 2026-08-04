# Moodle Downloader

English | [简体中文](README.zh-CN.md)

**Built for Monash University students.** It is written against Monash's
Moodle, Panopto and single sign-on; other institutions are out of scope.

Keeps every lecture slide, tutorial sheet and assignment brief published on
Moodle filed into weekly folders — by itself, all semester.
Lecture recordings are turned into readable transcripts, so a week's material
is text you can search, skim or paste into a chatbot. Late-released files like
tutorial solutions are picked up automatically on the next sync, and nothing is
ever downloaded twice.

```
Your folder/
├── FIT5003/
│   ├── Week 00 ... Week 12/
│   │   ├── lecture slides, worksheets, solutions ...
│   │   ├── Week 02 Summary.md      <- what happened this week
│   │   └── Transcripts/            <- lecture recordings as text
│   ├── Assignments/                <- briefs, rubrics + an assessment index
│   └── _Other/                     <- files that belong to no week
└── FIT5136/
    └── ...
```

![The app window](docs/app-dashboard.png)

## Getting started (Windows, no installation)

1. Download `MoodleDownloader.exe` from [Releases](../../releases) and put it
   in any folder. Windows may warn about an unknown publisher — that is normal
   for free unsigned software; choose **More info → Run anyway**.
2. Double-click it. Pick where files should be saved, then click **Load my
   courses from Moodle** and log in when the browser window appears — tick
   **"Keep me signed in"** so this rarely happens again.
3. Tick your courses and click **Finish and run first sync**.
4. Leave **Auto-sync** on. New files then arrive on their own, silently.

![Setup screen](docs/app-setup.png)

Your password is only ever typed into your university's own login page. The
app never sees it, and nothing is sent anywhere — there is no server and no
account. Session cookies stay in `%LOCALAPPDATA%\moodle-downloader`.

## How it works

- **Login** — a real browser window handles SSO and MFA. The session is saved
  and revived on later runs, so syncing is silent until it genuinely expires.
- **Crawling** — every course section is fetched, including nested
  sub-sections (Monash nests `Week N` inside a `Learning` section, with
  `Own-time` / `Real-time` blocks inside each week). Sub-sections inherit their
  parent's week.
- **Incremental sync** — a `.manifest.json` in your download folder records
  what has been fetched. Re-runs only download what is new; deleting a file
  locally makes it come back; a replaced file is saved beside the original.
- **Auto-sync** — runs at Windows login and every few hours after that, with
  no visible window.
- **Assignments** — briefs and rubrics attached by staff (never your own
  submissions) go to `UNIT/Assignments/<name>/`, alongside an auto-generated
  `Assessments.txt` listing every assessment with due dates and links.
- **Weekly notes** — each week folder gets a `Week NN Summary.md` (and a Word
  copy) listing that week's files, its lecture recordings and links, and the
  assessments coming up next. It is rewritten on every sync, so keep your own
  notes in a different file.
- **Transcripts** — no video is ever downloaded; only its captions. Panopto
  (one extra single sign-on) and YouTube recordings become readable
  transcripts in `Week NN/Transcripts/`. Recordings are found however staff
  published them: as links, as bare URLs typed into the page, and as videos
  embedded inside a page activity. Anything without captions — including Zoom
  cloud recordings — is named in the week note instead, so you know it exists.
- **AI summaries (optional)** — with an API key in `config.yaml`, each
  transcript also gets a Summary section. Any of Gemini (free tier), Claude,
  OpenAI, DeepSeek, Kimi, GLM, Qwen or a local Ollama model works; with no key
  the feature simply doesn't appear.

## Settings

Most people never need this, but `config.yaml` (next to the app) exposes:

| Key | Meaning |
| --- | --- |
| `root_dir` | Where course files are saved |
| `course_selection` | `manual` (fixed list) or `starred` (follows Moodle stars) |
| `sync_interval_hours` | Auto-sync interval, default `3` |
| `section_patterns` | Regexes matching a section title to a week, e.g. add `"module\\s*0*{week}\\b"` |
| `assignments_folder` | Set to `""` to skip assignments entirely |
| `weekly_notes` | `false` turns off the weekly summary notes |
| `transcripts` | `false` turns off caption downloads |
| `ai_provider` / `ai_api_key` | Optional AI summaries — see `config.example.yaml` for the provider list |

## Developers / macOS / Linux

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python run.py            # GUI
python run.py sync       # headless sync, for cron or Task Scheduler
```

The app drives a real browser via Playwright, using system Edge or Chrome when
available; otherwise run `playwright install chromium` once. macOS and Linux
should work but are not regularly tested.

Build the Windows executable:

```bash
pyinstaller --onefile --noconsole --name MoodleDownloader ^
  --version-file version_info.txt ^
  --collect-all playwright --collect-all customtkinter run.py
```

## FAQ

**A browser window opened and asked me to log in.** The saved session expired
— log in there and the sync continues by itself. Don't close the window.

**My unit uses "Module 3" instead of "Week 3".** Add a pattern to
`section_patterns` in `config.yaml`.

**Files went to `_Other/`.** That section's title matched no week pattern —
same fix as above.

**I moved the exe and auto-sync stopped.** Turn Auto-sync off and on again to
re-register the new location.

**Is this allowed?** It downloads material from units you are enrolled in,
through your own login, for personal study — the same files you could click
one by one.

## License

MIT
