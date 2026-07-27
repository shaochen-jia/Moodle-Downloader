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
