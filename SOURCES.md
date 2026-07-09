# Data Sources

[简体中文](#数据来源)

TypEng can use several third-party dictionary resources. Each keeps its own
license; keep the original license notices with any packaged release.

## ECDICT

TypEng can import `ecdict.csv` from ECDICT to generate tagged vocabulary libraries.

- Source: https://github.com/skywind3000/ECDICT
- License: MIT License, as stated by the ECDICT project
- Used fields: `word`, `phonetic`, `definition`, `translation`, `pos`, `tag`, `bnc`, `frq`

TypEng can read bundled ECDICT data from `resources/ecdict.csv`. This is the preferred release path: users click a preset library button and TypEng creates the selected library from the packaged CSV.

During development, if `resources/ecdict.csv` is not present, TypEng can fall back to a cached `data/ecdict.csv`, then try downloading from ECDICT. Users can also provide a local `ecdict.csv` file from the edit view.

Supported tags currently include:

- `zk` -> 中考
- `gk` -> 高考
- `cet4` -> CET4
- `cet6` -> CET6
- `ky` / `kaoyan` -> 考研
- `ielts` -> IELTS
- `toefl` -> TOEFL
- `gre` -> GRE

## Open English WordNet

Used as the built-in source for English definitions and example sentences behind
the "auto examples" feature. Release packages already include this file, so auto
examples work out of the box.

- Source: https://github.com/globalwordnet/english-wordnet (site: https://en-word.net)
- Download: https://en-word.net/static/english-wordnet-2025-json.zip
- License: CC-BY 4.0, as stated by the Open English WordNet project
- Expected location: `resources/wordnet/english-wordnet-2025-json.zip`

## Wiktionary (Kaikki)

The English Wiktionary JSONL export from Kaikki gives the richest, most natural
example sentences and part-of-speech-matched definitions. It is large (about
3 GB), so it is **not** included in release packages — you add it yourself if you
want the best example coverage. TypEng works without it (WordNet covers most
common words); Wiktionary simply improves example quality and breadth.

- Source: https://kaikki.org/dictionary/English/
- Download (direct): https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl
  (`kaikki.org-dictionary-English.jsonl`, about 3 GB)
- License: Wiktionary content is CC-BY-SA 4.0; the Kaikki extraction tooling
  (wiktextract) is separately licensed. Keep attribution with any redistribution.
- Expected location (either works):
  - next to the app executable: `kaikki.org-dictionary-English.jsonl`
  - or `resources/wiktionary/kaikki.org-dictionary-English.jsonl`

A step-by-step Chinese install guide is shipped with releases as
`词典安装指南.pdf` (source: `docs/dictionary_setup.zh-CN.md`).

---

# 数据来源

TypEng 可以使用多个第三方词典资源。每个资源都保留各自的许可证；在任何打包发行版中都请一并保留原始许可证声明。

## ECDICT

TypEng 可以导入 ECDICT 的 `ecdict.csv` 来生成带标签的词库（四六级、考研、雅思等）。

- 来源：https://github.com/skywind3000/ECDICT
- 许可证：ECDICT 项目声明为 MIT License
- 使用字段：`word`、`phonetic`、`definition`、`translation`、`pos`、`tag`、`bnc`、`frq`

TypEng 会优先读取打包好的 `resources/ecdict.csv`。这是推荐的发行方式：用户点击预设词库按钮，TypEng 就用打包的 CSV 创建对应词库。

开发时如果没有 `resources/ecdict.csv`，TypEng 会依次尝试缓存的 `data/ecdict.csv`，再尝试从 ECDICT 在线下载。用户也可以在编辑界面提供本地的 `ecdict.csv` 文件。

## Open English WordNet（英文词网）

作为「自动填充例句」功能的**内置**英文释义和例句来源。发行包已经包含这个文件，所以自动例句开箱即用。

- 来源：https://github.com/globalwordnet/english-wordnet （站点：https://en-word.net）
- 下载：https://en-word.net/static/english-wordnet-2025-json.zip
- 许可证：Open English WordNet 项目声明为 CC-BY 4.0
- 存放位置：`resources/wordnet/english-wordnet-2025-json.zip`

## Wiktionary（Kaikki 提取版）

来自 Kaikki 的英文维基词典 JSONL 导出文件，能提供最丰富、最自然的例句和按词性匹配的英文释义。由于文件很大（约 3 GB），它**不**包含在发行包里——如果你想要最好的例句覆盖，需要自行添加。没有它 TypEng 也能正常工作（WordNet 已覆盖大部分常见词），Wiktionary 只是进一步提升例句的质量和广度。

- 来源：https://kaikki.org/dictionary/English/
- 下载（直链）：https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl
  （文件名 `kaikki.org-dictionary-English.jsonl`，约 3 GB）
- 许可证：维基词典内容为 CC-BY-SA 4.0；Kaikki 的提取工具（wiktextract）单独授权。二次分发时请保留署名。
- 存放位置（任选其一）：
  - 放在应用可执行文件同级目录：`kaikki.org-dictionary-English.jsonl`
  - 或放在 `resources/wiktionary/kaikki.org-dictionary-English.jsonl`

发行包里附带了一份图文版中文安装指南 `词典安装指南.pdf`（源文件：`docs/dictionary_setup.zh-CN.md`）。
