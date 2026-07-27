# Moodle Downloader(Moodle 课件自动下载器)

[English](README.md) | 简体中文

自动把你的(Monash)Moodle 课程文件下载到整齐的周文件夹里——
`FIT5003/Week 01`、`Week 02`……并在整个学期持续保持更新。晚发布的文件
(习题答案、补充讲义)会在下一次运行时自动补上。开启每日自动同步后,
你再也不用手动去 Moodle 点下载了。

```
你的文件夹/
├── FIT5003/
│   ├── Week 00 ... Week 12/     <- 文件自动归入对应的周
│   └── _Other/                  <- 不属于任何周的文件
└── FIT5136/
    └── ...
```

## 普通用户(Windows,无需安装任何东西)

1. 从 [Releases](../../releases) 下载 `MoodleDownloader.exe`,放到任意文件夹;
2. 双击运行,选择 **setup(首次设置)**:会弹出一个浏览器窗口——你自己登录
   Moodle(记得勾选 **"Keep me signed in / 保持登录"**),然后从列表里
   选择你的课程。**不需要抄课程 ID,不需要改配置文件**;
3. 选择 **Sync course files now(立即同步)**——完成,文件出现在你指定的文件夹;
4. 建议再选择 **Turn ON auto-sync(开启自动同步)**,以后每次开机登录
   Windows 都会自动同步,彻底不用管。

你的密码只会输入在大学官方登录页面里,本工具不存储、也看不到你的密码。
登录 cookie 保存在本机的 `%LOCALAPPDATA%\moodle-downloader`。

## 逐步教学(你实际会看到的每一个画面)

### 第一次打开

双击 `MoodleDownloader.exe`。

> Windows 第一次可能弹出蓝色的 **"Windows 已保护你的电脑"** 提示——这是
> 免费软件没有付费签名证书的正常现象。点 **更多信息 → 仍要运行** 即可。

之后出现一个终端窗口,显示主菜单:

```
=== Moodle Downloader ===
  [1] Sync course files now
  [2] First-time setup / change courses
  [3] Turn ON auto-sync (runs at Windows login + daily)
  [4] Turn OFF auto-sync
  [5] Exit
Choose an option:
```

五个选项的意思:**[1] 立即同步文件、[2] 首次设置/更换课程、[3] 开启自动
同步(开机登录时+每天)、[4] 关闭自动同步、[5] 退出**。
输入数字后按**回车**。全新安装先输 `2`。
(如果没设置过就直接按 `1`,程序也会自动带你先做设置。)

### 选项 [2] —— 首次设置

**第一个问题——你的 Moodle 网址:**

```
=== Moodle Downloader - first-time setup ===

Moodle address (press Enter if you are at Monash) [https://learning.monash.edu]:
```

Monash 学生:**直接回车**。其他学校:先粘贴你学校的 Moodle 网址。

**第二个问题——文件存到哪里:**

```
Folder where course files should be saved [C:\Users\you\MoodleFiles]:
```

输入(或粘贴)你想要的文件夹完整路径,比如
`C:\Users\you\Desktop\Uni 2026`,然后回车;也可以直接回车用方括号里的
默认位置。文件夹不存在会自动创建。
小技巧:可以在 Windows 资源管理器的地址栏里复制文件夹路径。

**登录环节:**

```
Now fetching your course list from Moodle.
If a browser window opens, log in with your university account
(tick 'Keep me signed in' so this rarely happens again).
```

此时会发生两种情况之一:

- **第一次使用**:弹出浏览器窗口,停在学校官方登录页。你自己完成登录
  (账号、密码、MFA),**记得勾选 "Keep me signed in / 保持登录"**。
  登录完窗口会自动关闭。密码只输入在学校自己的页面里,工具看不到。
- **最近登录过**:浏览器可能一闪而过、几秒内自动关闭——那是工具在确认
  你保存的登录状态还有效,**不需要你做任何事**,这是正常现象。

**选择课程:**

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

你**注册过的所有课程**都会列出来,**最新学期排最前**,所以本学期的课就在
最上面几行。带 `*` 号的是你自己在 Moodle 上加过星标(starred)的课。

- 输入例如 `1,2,3,4` 回车 → 固定同步这几门课;
- 或输入 `star` 回车 → 永远同步你在 Moodle 上加星的课(以后在 Moodle
  里改星标,工具自动跟随;像 "IT Student Portal" 这类加了星但不是课程的
  页面会被自动过滤掉)。

```
Selected: FIT5163, FIT5234, FIT5136, FIT5003

Setup complete! Settings saved to C:\...\config.yaml
```

设置完成,回到主菜单。

### 选项 [1] —— 立即同步

```
=== FIT5003 (https://learning.monash.edu/course/view.php?id=4***8) ===

=== FIT5136 (https://learning.monash.edu/course/view.php?id=4***3) ===
  [Week 3] Wrap-up - 1 item(s)
    + C:\Users\you\Uni 2026\FIT5136\Week 03\use-case-satzinger-jackson-burd.pdf

=== FIT5163 (https://learning.monash.edu/course/view.php?id=4***9) ===
  [Week 1] Real-time - 3 item(s)
    + C:\Users\you\Uni 2026\FIT5163\Week 01\LN01_intro.pdf
    ...

Done. 10 new file(s) downloaded.
```

- 每一行开头的 `+` 表示**新下载**的文件,后面就是它落地的位置;
- 只显示课程名、下面空空的(如上面的 FIT5003),说明这门课还没发布文件;
- 紧接着再跑一次会显示 `Done. 0 new file(s) downloaded.`——任何文件
  都不会被重复下载。

如果保存的登录状态过期了,同步前会先显示:

```
Session expired or first run - opening a browser window so you can log in (SSO + MFA)...
Please log in to Moodle in the browser window (waiting up to 10 minutes)...
TIP: tick 'Keep me signed in' on the Okta page so future runs skip MFA.
(Don't close the window - it closes by itself when the download finishes.)
```

在弹出的窗口里重新登录即可,同步会自动继续。**不要手动关那个窗口**,
它下载完会自己关。

### 选项 [3] —— 开启自动同步

```
Done - your files now sync automatically:
  - every time you log in to Windows (1 minute after logon)
  - plus a daily 09:00 run if the PC is already on
(A small console window appears briefly while it runs.)
```

意思是:**每次开机登录 Windows 后 1 分钟自动同步一次**,外加电脑开着时
每天 9 点一次。有些学校/公司管控的电脑禁止注册计划任务,工具会自动改用
备用方案,并显示:

```
Done - your files now sync automatically every time you log in to Windows.
```

对你来说效果一样:登录 Windows 大约一分钟后,会有一个小终端窗口自己
打开、同步、自己关闭。所以就算你今天晚上才第一次开电脑,当天的新文件
照样会到。

注意:自动同步记录的是 exe 当前的位置。以后如果**挪动了 exe**,进菜单
按 `4` 再按 `3` 重新登记一次即可。

### 选项 [4] —— 关闭自动同步

```
Auto-sync removed.
```

### 选项 [5] —— 退出

关闭程序。(直接点窗口右上角的 X 也一样。已开启的自动同步不受影响——
它不需要这个窗口开着。)

### 一次完整真实流程(从头到尾)

下面是一次完整的首次使用全过程(路径已匿名化)。你的屏幕会和这个一模
一样——**你**需要输入的只有:`2`、回车、回车或文件夹路径、`1,2,3,4`、
`1`、`5`,一共六次:

> ⚠️ **特别提示:输入课程编号时请用英文逗号 `1,2,3,4`,不要用中文逗号
> `1，2，3，4`。**(工具其实也能自动纠正中文逗号,但养成习惯更稳妥。
> 切换到英文输入法再输入即可。)

```
=== Moodle Downloader ===
  [1] Sync course files now
  [2] First-time setup / change courses
  [3] Turn ON auto-sync (runs at Windows login + daily)
  [4] Turn OFF auto-sync
  [5] Exit
Choose an option: 2

=== Moodle Downloader - first-time setup ===

Moodle address (press Enter if you are at Monash) [https://learning.monash.edu]:
Folder where course files should be saved [C:\Users\you\MoodleFiles]: C:\Users\you\Desktop\Uni 2026

Now fetching your course list from Moodle.
If a browser window opens, log in with your university account
(tick 'Keep me signed in' so this rarely happens again).

Found 23 enrolled courses (* = starred on Moodle):

   1. * FIT5163 Introduction to cryptography for cybersecurity - S2 2026
   2. * FIT5234 Advanced business information systems analysis and design - S2 2026
   3. * FIT5136 Software engineering - S2 2026
   4. * FIT5003 Software security - S2 2026
   5.   FIT5057 Project management - S1 2026
   6.   FIT5129 Cyber operations - S1 2026
   ...           (你注册过的每一门课,最新学期在最上面)
  23. * IT Student Portal

Which courses should be synced?
  - numbers separated by commas, e.g.:  1,2,3,4
  - or type  star  to always sync the courses you star on Moodle
> 1,2,3,4

Selected: FIT5163, FIT5234, FIT5136, FIT5003

Setup complete! Settings saved to C:\Users\you\Desktop\MoodleDownloader\config.yaml

=== Moodle Downloader ===
  [1] Sync course files now
  [2] First-time setup / change courses
  [3] Turn ON auto-sync (runs at Windows login + daily)
  [4] Turn OFF auto-sync
  [5] Exit
Choose an option: 1

=== FIT5163 (https://learning.monash.edu/course/view.php?id=00000) ===
  [Week 1] Own-time - 2 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5163\Week 01\Week 1  PollEv Questions and Answers.pdf
    + C:\Users\you\Desktop\Uni 2026\FIT5163\Week 01\Essential Information for FIT Students.pdf
  [Week 1] Real-time - 3 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5163\Week 01\LN01_intro.pdf
    + C:\Users\you\Desktop\Uni 2026\FIT5163\Week 01\LN00_unitinfo.pdf
    + C:\Users\you\Desktop\Uni 2026\FIT5163\Week 01\Applied 1.docx.pdf

=== FIT5234 (https://learning.monash.edu/course/view.php?id=00000) ===
  [Week 1] Real-time - 4 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5234\Week 01\FIT5234 Seminar 1 - Intra- and Inter-organizational BIS.pdf
    ...
  [Week 2] Real-time - 2 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5234\Week 02\FIT5234 Seminar - 2 Intra-organizational BIS.pdf
    ...

=== FIT5136 (https://learning.monash.edu/course/view.php?id=00000) ===
  [Week 3] Wrap-up - 1 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5136\Week 03\use-case-satzinger-jackson-burd.pdf
  [Week 8] Wrap-up - 1 item(s)
    + C:\Users\you\Desktop\Uni 2026\FIT5136\Week 08\Michael Quinn Ch 8.pdf

=== FIT5003 (https://learning.monash.edu/course/view.php?id=00000) ===

Done. 13 new file(s) downloaded.

=== Moodle Downloader ===
  [1] Sync course files now
  [2] First-time setup / change courses
  [3] Turn ON auto-sync (runs at Windows login + daily)
  [4] Turn OFF auto-sync
  [5] Exit
Choose an option: 5
```

到此结束——以后要么偶尔双击按个 `1`,要么按一次 `3` 开启自动同步,
彻底忘掉这件事。

## 开发者 / macOS / Linux

需要 Python 3.10+。

```bash
git clone <本仓库> && cd moodle-downloader
pip install -r requirements.txt
python run.py            # 交互菜单(设置、同步……)
python run.py sync       # 或直接同步
```

本工具通过 Playwright 驱动真实浏览器。Windows 上可直接使用系统自带的
Edge,无需下载浏览器;其他系统若既没有 Chrome 也没有 Playwright 浏览器,
运行一次 `playwright install chromium` 即可。macOS/Linux 理论上可用,
但未经常态化测试。

## 工作原理

- **登录**:第一次运行会弹出真实浏览器窗口,你通过学校自己的 SSO + MFA
  登录。cookie(包括会话 cookie)会保存在本地并在后续运行时自动恢复,
  所以之后的同步都是静默无窗口的——直到会话真正过期,窗口才会再次弹出。
- **抓取**:抓取每一个课程 section 页面,包括嵌套的子 section
  (Monash 的课程格式把 `Week N` 嵌在 `Learning` 里,每周里还有
  `Own-time` / `Real-time` 板块——子 section 自动归入所属的周)。
- **周匹配**:section 标题按 `Week N` / `Topic N` 匹配
  (可在 `config.yaml` 里自定义正则)。
- **增量下载**:下载文件夹里的 `.manifest.json` 记录已下载的每个文件。
  重复运行只下载新文件,绝不重复下载。本地删掉某文件,下次运行会自动补回。
  老师替换了文件时,新版本会下载到旧版本旁边(不覆盖)。
- **星标模式**:可以不固定课程列表,改为同步你在 Moodle 上加星标的课程
  ——换学期时只需在 Moodle 里改星标,工具自动跟随。

## 常见问题

**浏览器窗口关掉了 / 我不小心关了。** 重新运行同步即可。

**提示 "Could not log in"。** 重新运行同步,并在 10 分钟内完成登录。
不要手动关窗口——它会自己关闭。

**我的课用的是 "Module 3" 而不是 "Week 3"。** 在 `config.yaml` 的
`section_patterns` 里加一条,例如 `"module\\s*0*{week}\\b"`。

**文件跑到 `_Other/` 里去了。** 说明那个 section 的标题没匹配到任何
周数——解决方法同上。

**这样做合规吗?** 本工具只通过你本人的登录,下载你已注册课程的资料,
供个人学习使用——和你自己一个一个点下载得到的文件完全相同。

## 自行打包 exe

```bash
pip install pyinstaller
pyinstaller --onefile --name MoodleDownloader --collect-all playwright run.py
```

## 许可证

MIT
