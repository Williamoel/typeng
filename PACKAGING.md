# Packaging typeng For Windows

[简体中文](#windows-打包说明)

typeng is not packaged as a Windows executable yet. This document records the intended packaging workflow so the project can later ship as a simple local app:

```text
download zip -> extract -> double-click typeng.exe -> browser opens typeng
```

The recommended first packaging path is PyInstaller. typeng can remain a local Flask app internally: the executable starts the local server, waits until it is ready, and opens the browser at `http://127.0.0.1:5000`.

## Target Release Layout

A user-facing zip package should look roughly like this:

```text
typeng/
  typeng.exe
  data/
  resources/
    ecdict.csv
    wordnet/
      english-wordnet-2025-json.zip
    wiktionary/
      kaikki.org-dictionary-English.jsonl
  samples/
  README.zh-CN.md
  README.md
  SOURCES.md
```

`data/` stores the local SQLite database and generated lookup caches. It should remain writable after extraction.

Large dictionary resources may be shipped in release packages instead of committed directly to the repository. Keep the original source and license notices with every packaged release.

## Packaging Entry Point

The project should add a small launcher file, for example `run_typeng.py`, before producing the executable.

The launcher should:

1. Resolve the application root correctly in both source mode and PyInstaller mode.
2. Start the Flask app on `127.0.0.1:5000`.
3. If port `5000` is already in use, choose another local port.
4. Open the default browser automatically.
5. Keep the process alive until the user closes the console window or the app exits.

PyInstaller exposes bundled files through `sys._MEIPASS`; the launcher and app should account for that when locating `templates/`, `static/`, `resources/`, `samples/`, and `data/`.

## Build Steps

Run these commands on Windows, preferably from PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

After adding `run_typeng.py`, build with a directory-style bundle first:

```powershell
pyinstaller ^
  --name typeng ^
  --onedir ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "resources;resources" ^
  --add-data "samples;samples" ^
  --add-data "README.md;." ^
  --add-data "README.zh-CN.md;." ^
  --add-data "SOURCES.md;." ^
  run_typeng.py
```

Prefer `--onedir` for the first public release. It starts faster and makes bundled resources easier to inspect than a single-file executable.

After building, test:

```powershell
.\dist\typeng\typeng.exe
```

The browser should open automatically. If it does not, manually open the local URL printed by the launcher.

## Release Checklist

- Start `typeng.exe` on a clean Windows machine.
- Confirm the browser opens automatically.
- Confirm preset libraries can be created from packaged ECDICT data.
- Confirm Wiktionary / WordNet examples and definitions work if those resources are included.
- Confirm new words, learned words, wrong words, and review progress persist after closing and reopening.
- Confirm `data/` is writable inside the extracted folder.
- Confirm the app still works without internet access, except for optional external audio behavior if used.
- Include `README.md`, `README.zh-CN.md`, `SOURCES.md`, and resource license notices.
- Zip the whole `dist/typeng/` folder, not only `typeng.exe`.

## Notes

The executable is a convenience wrapper around a local web app. It should not require WSL, a manually created virtual environment, or command-line Flask startup from the end user.

For long-term polish, typeng may later use a desktop shell such as Tauri or Electron, but PyInstaller is the simplest path that matches the current Python codebase.

---

# Windows 打包说明

typeng 目前还没有真正打包成 Windows 可执行文件。这份文档先记录预期的打包方案，后续目标是让普通用户可以这样使用：

```text
下载 zip -> 解压 -> 双击 typeng.exe -> 浏览器自动打开 typeng
```

第一版建议使用 PyInstaller。typeng 内部仍然可以是本地 Flask 应用：exe 负责启动本地服务，等待服务可用，然后自动打开浏览器访问 `http://127.0.0.1:5000`。

## 目标发行目录

面向用户的 zip 包大致应该长这样：

```text
typeng/
  typeng.exe
  data/
  resources/
    ecdict.csv
    wordnet/
      english-wordnet-2025-json.zip
    wiktionary/
      kaikki.org-dictionary-English.jsonl
  samples/
  README.zh-CN.md
  README.md
  SOURCES.md
```

`data/` 用来保存本地 SQLite 数据库和生成的查询缓存。用户解压后，这个目录必须保持可写。

较大的词典资源可以只放进 release 压缩包，不一定直接提交到仓库。每次发布时都要保留资源来源和许可证说明。

## 打包入口

在真正打包前，项目应该增加一个很小的启动文件，例如 `run_typeng.py`。

这个启动文件需要负责：

1. 在源码运行和 PyInstaller 运行两种情况下都能正确找到项目根目录。
2. 在 `127.0.0.1:5000` 启动 Flask 应用。
3. 如果 `5000` 端口已被占用，就自动选择另一个本地端口。
4. 自动打开系统默认浏览器。
5. 让进程保持运行，直到用户关闭窗口或应用退出。

PyInstaller 会通过 `sys._MEIPASS` 暴露打包后的临时资源目录；启动器和应用在定位 `templates/`、`static/`、`resources/`、`samples/`、`data/` 时需要考虑这一点。

## 打包步骤

建议在 Windows PowerShell 中执行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

增加 `run_typeng.py` 之后，先使用目录形式打包：

```powershell
pyinstaller ^
  --name typeng ^
  --onedir ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "resources;resources" ^
  --add-data "samples;samples" ^
  --add-data "README.md;." ^
  --add-data "README.zh-CN.md;." ^
  --add-data "SOURCES.md;." ^
  run_typeng.py
```

第一版公开发布建议优先使用 `--onedir`，它比单文件 exe 启动更快，也更方便检查随包资源是否完整。

打包后测试：

```powershell
.\dist\typeng\typeng.exe
```

正常情况下浏览器会自动打开。如果没有自动打开，可以手动访问启动器打印出的本地地址。

## 发布前检查

- 在干净的 Windows 环境中启动 `typeng.exe`。
- 确认浏览器能自动打开。
- 确认可以从打包的 ECDICT 数据创建预设词库。
- 如果随包包含 Wiktionary / WordNet，确认英文释义和例句可用。
- 确认新增单词、已学词、错词和复习进度在关闭重开后仍然保留。
- 确认解压目录中的 `data/` 可写。
- 确认离线状态下应用仍然可以使用，除非使用了可选的外部音频来源。
- 随包包含 `README.md`、`README.zh-CN.md`、`SOURCES.md` 和资源许可证说明。
- 打包 zip 时压缩整个 `dist/typeng/` 文件夹，而不是只压缩 `typeng.exe`。

## 说明

这个 exe 本质上是本地网页应用的便捷启动器。最终用户不应该需要 WSL、手动创建虚拟环境，或者输入 Flask 启动命令。

长期来看，typeng 也可以考虑 Tauri 或 Electron 这类桌面外壳；但从当前 Python 代码出发，PyInstaller 是最直接、成本最低的路径。
