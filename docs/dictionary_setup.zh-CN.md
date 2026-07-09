# TypEng 词典安装指南

本指南教你为 TypEng 添加词典资源，让「英文释义」和「自动填充例句」等功能更完整。
全程不需要编程，按步骤操作即可。

---

## 一分钟了解

TypEng 用到三种词典资源，重要程度和是否需要你手动安装如下：

| 资源 | 作用 | 需要你手动装吗？ | 大小 |
| --- | --- | --- | --- |
| WordNet | 自动填充例句、英文释义（内置） | 否，发行包已自带 | 约 10 MB |
| ECDICT | 生成 CET4/6、考研、雅思等预设词库 | 一般不需要 | 约 60 MB |
| Wiktionary | 提供最丰富、最自然的例句 | 需要，想要更好例句时自行添加 | 约 3 GB |

结论：**只想正常使用，什么都不用装**。想要最好的例句质量，再按下面的说明添加 Wiktionary。

---

## 一、先找到 TypEng 的安装文件夹

你从发行页下载的压缩包解压后，会得到一个文件夹，里面有：

```
TypEng/
├─ typeng.exe          ← Windows 上双击运行的程序（Mac 上是 typeng）
├─ data/               ← 你的学习数据
├─ resources/          ← 词典资源放这里
│  ├─ wordnet/
│  └─ wiktionary/
├─ samples/
└─ 词典安装指南.pdf     ← 就是本文件
```

后面所有「放到哪里」的说明，都是相对这个文件夹来说的。

---

## 二、安装 Wiktionary（可选，但强烈推荐）

Wiktionary 能大幅提升例句的数量和质量。它有约 3 GB，所以没有打包进发行包，需要你自己下载一次。

### 第 1 步：下载

1. 用浏览器打开下载页：

   **https://kaikki.org/dictionary/English/**

2. 在页面顶部找到这样一条链接（英文）：

   **“Download JSON data for all senses”**

   点击它，就会开始下载一个名为
   **`kaikki.org-dictionary-English.jsonl`** 的文件（约 3 GB，请耐心等待，
   建议在网络稳定时下载）。

> 提示：文件很大，下载完请确认文件名结尾是 `.jsonl`。如果浏览器把它保存成
> `.txt` 或加了 `(1)` 之类的后缀，请把文件名改回
> `kaikki.org-dictionary-English.jsonl`。

### 第 2 步：放到正确位置

把下载好的 `kaikki.org-dictionary-English.jsonl` 放到 **以下任意一个位置**：

- **方式 A（最简单）**：直接放在 `typeng.exe` 旁边，也就是 TypEng 文件夹的根目录：

  ```
  TypEng/
  ├─ typeng.exe
  └─ kaikki.org-dictionary-English.jsonl   ← 放这里
  ```

- **方式 B**：放进 `resources/wiktionary/` 文件夹：

  ```
  TypEng/
  └─ resources/
     └─ wiktionary/
        └─ kaikki.org-dictionary-English.jsonl   ← 或者放这里
  ```

两种方式二选一即可，效果相同。

### 第 3 步：重新启动 TypEng

如果 TypEng 正在运行，先关闭窗口，再重新双击 `typeng.exe`。之后使用「自动填充例句」
时，就会用到 Wiktionary 里更丰富的例句了。

> 首次使用会稍慢一点：TypEng 需要先给这个大文件建立一次索引，之后就会很快。

---

## 三、（进阶）替换或添加 WordNet

发行包已内置 WordNet，正常情况下你不用管这一节。如果你想更新到新版本：

1. 下载：**https://en-word.net/static/english-wordnet-2025-json.zip**
2. 放到：`resources/wordnet/english-wordnet-2025-json.zip`（覆盖原文件）
3. 重启 TypEng。

---

## 四、（进阶）添加 ECDICT 以生成预设词库

如果点击 CET4、考研、雅思等预设词库时提示找不到 ECDICT 数据，可以自行添加：

1. 下载：打开 **https://github.com/skywind3000/ECDICT**，按项目说明获取
   `ecdict.csv`（约 60 MB）。
2. 放到：`resources/ecdict.csv`。
3. 重启 TypEng，再点击预设词库按钮即可。

你也可以在 TypEng 的「编辑词库 → 导入 ECDICT」里，直接选择本地的 `ecdict.csv` 文件。

---

## 五、常见问题

**问：点了「自动填充例句」，提示找不到词典源怎么办？**
答：说明程序没找到 Wiktionary 或 WordNet 文件。发行包本应自带 WordNet；如果你用的是
自己从源码构建的版本，或删掉了 `resources/wordnet/` 里的文件，请按第三节重新放入
WordNet；想要更好例句就按第二节安装 Wiktionary。放好后记得**重启 TypEng**。

**问：文件放对位置了，但还是没生效？**
答：请确认三点：①文件名完全正确（尤其结尾的 `.jsonl` / `.zip`）；②放的是正确的文件夹；
③放好后重新启动了 TypEng。

**问：我需要联网才能用 TypEng 吗？**
答：不需要。词典文件下载一次放到本地后，TypEng 完全在你自己的电脑上离线运行。唯一会联网的
是「自动发音」功能（向有道请求单词读音），关闭自动发音即可完全离线。

**问：这些词典可以随便分发吗？**
答：它们各自有版权许可（见 `SOURCES.md`）。个人学习使用没问题；如果你要二次分发，请保留
原始的署名和许可证声明。

---

如果还有问题，欢迎在项目仓库提交 issue：
https://github.com/Williamoel/typeng/issues
