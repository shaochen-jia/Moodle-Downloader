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

## Step-by-step walkthrough (what you will actually see)

### First launch

Double-click `MoodleDownloader.exe`.

> Windows may show a blue **"Windows protected your PC"** screen the first
> time — that is normal for free software without a paid signing certificate.
> Click **More info → Run anyway**.

A terminal window opens with the main menu:

```
=== Moodle Downloader ===
  [1] Sync course files now
  [2] First-time setup / change courses
  [3] Turn ON auto-sync (runs at Windows login + daily)
  [4] Turn OFF auto-sync
  [5] Exit
Choose an option:
```

Type a number and press **Enter**. On a brand-new install, start with `2`.
(If you press `1` without any setup, it starts the setup for you anyway.)

### Option [2] — First-time setup

**Question 1 — your Moodle address:**

```
=== Moodle Downloader - first-time setup ===

Moodle address (press Enter if you are at Monash) [https://learning.monash.edu]:
```

Monash students: just press **Enter**. Other universities: paste your Moodle
URL first.

**Question 2 — where files should go:**

```
Folder where course files should be saved [C:\Users\you\MoodleFiles]:
```

Type (or paste) the full path of any folder you like, e.g.
`C:\Users\you\Desktop\Uni 2026`, then press Enter — or just press Enter to
accept the suggested default. The folder is created if it doesn't exist.
Tip: you can copy a folder's path from the address bar of Windows Explorer.

**The login moment:**

```
Now fetching your course list from Moodle.
If a browser window opens, log in with your university account
(tick 'Keep me signed in' so this rarely happens again).
```

One of two things happens now:

- **Very first run**: a browser window opens on your university's login page.
  Log in yourself (username, password, MFA) and tick **"Keep me signed in"**.
  The window closes by itself when done. Your password goes only into the
  university's own page — the tool never sees it.
- **Already logged in recently**: the browser may flash open and close within
  a few seconds. That is the tool confirming your saved login still works —
  nothing for you to do.

**Choosing your courses:**

```
Found 23 enrolled courses (* = starred on Moodle):

   1. * FIT5163 Introduction to cryptography for cybersecurity - S2 2026
   2. * FIT5234 Advanced business information systems analysis and design - S2 2026
   3. * FIT5136 Software engineering - S2 2026
   4. * FIT5003 Software security - S2 2026
   5.   Yearly refresher of key Monash principles and values 2026
   6.   FIT4005-FIT5125 IT research and innovation methods - S1 2026
   ...
  23. * IT Student Portal

Which courses should be synced?
  - numbers separated by commas, e.g.:  1,2,3,4
  - or type  star  to always sync the courses you star on Moodle
> 
```

Every course you have ever enrolled in is listed, **newest semester first**,
so this semester's units are at the top. A `*` means you starred that course
on Moodle yourself.

- Type e.g. `1,2,3,4` and press Enter → those exact units are synced.
- Or type `star` → the tool always syncs whatever you have starred on Moodle
  (change stars on Moodle, the tool follows; starred non-course pages like
  "IT Student Portal" are filtered out automatically).

```
Selected: FIT5163, FIT5234, FIT5136, FIT5003

Setup complete! Settings saved to C:\...\config.yaml
```

You are back at the menu.

### Option [1] — Sync course files now

```
=== FIT5003 (https://learning.monash.edu/course/view.php?id=45038) ===

=== FIT5136 (https://learning.monash.edu/course/view.php?id=46903) ===
  [Week 3] Wrap-up - 1 item(s)
    + C:\Users\you\Uni 2026\FIT5136\Week 03\use-case-satzinger-jackson-burd.pdf

=== FIT5163 (https://learning.monash.edu/course/view.php?id=46949) ===
  [Week 1] Real-time - 3 item(s)
    + C:\Users\you\Uni 2026\FIT5163\Week 01\LN01_intro.pdf
    ...

Done. 10 new file(s) downloaded.
```

- Every line starting with `+` is a **newly downloaded** file, shown with its
  final location.
- A course showing only its header (like FIT5003 above) simply has no files
  published yet.
- Run it again straight away and you get `Done. 0 new file(s) downloaded.` —
  nothing is ever downloaded twice.

If your saved login has expired, you will see this first:

```
Session expired or first run - opening a browser window so you can log in (SSO + MFA)...
Please log in to Moodle in the browser window (waiting up to 10 minutes)...
TIP: tick 'Keep me signed in' on the Okta page so future runs skip MFA.
(Don't close the window - it closes by itself when the download finishes.)
```

Just log in in the window that opened; the sync continues by itself.

### Option [3] — Turn ON auto-sync

```
Done - your files now sync automatically:
  - every time you log in to Windows (1 minute after logon)
  - plus a daily 09:00 run if the PC is already on
(A small console window appears briefly while it runs.)
```

On some university-managed laptops Windows blocks scheduled tasks; the tool
detects this and falls back automatically, printing instead:

```
Done - your files now sync automatically every time you log in to Windows.
```

Either way the result is the same for you: about a minute after you log in to
Windows, a small console window opens, syncs, and closes itself. So even if
you first turn on your PC at night, that day's new files still arrive.

Note: auto-sync remembers where the exe is. If you later **move** the exe,
run option `4` then `3` again to re-register the new location.

### Option [4] — Turn OFF auto-sync

```
Auto-sync removed.
```

### Option [5] — Exit

Closes the program. (Closing the window with the X button is fine too.
Auto-sync, if enabled, keeps working — it does not need the window open.)

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
