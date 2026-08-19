# Data Sources

[简体中文](#数据来源)

TypEng can use several third-party dictionary resources. Each keeps its own
license; keep the original license notices with any packaged release.

## Interface font

The web interface bundles the Simplified Chinese subset of Noto Sans SC so its
Chinese typography remains consistent on systems without CJK fonts.

- Source: https://fonts.google.com/noto/specimen/Noto+Sans+SC
- Package: `@fontsource/noto-sans-sc`
- License: SIL Open Font License 1.1 (included in `static/fonts/OFL.txt`)

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

## EFLLex

Used as an independent A1-C1 frequency profile for vocabulary difficulty audits.
The original TSV and derived profile remain separate from TypEng's MIT-licensed code.

- Source: https://cental.uclouvain.be/cefrlex/efllex/download/
- Paper: Dürlich and François, *EFLLex: A Graded Lexical Resource for Learners of English as a Foreign Language*, LREC 2018
- License: CC BY-NC-SA 4.0
- Expected location: `resources/efllex/EFLLex.tsv`
- Transformation: underscores in multiword expressions are normalized to spaces; a provisional audit level records the earliest non-zero level, while all source frequencies remain available

## Wiktionary (Kaikki)

The English Wiktionary JSONL export from Kaikki supplies part-of-speech-matched
definitions and examples. It is large (about 3 GB), so it is **not** included in
release packages; add it when automatic examples are needed.

- Source: https://kaikki.org/dictionary/English/
- Download (direct): https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl
  (`kaikki.org-dictionary-English.jsonl`, about 3 GB)
- License: Wiktionary content is CC-BY-SA 4.0; the Kaikki extraction tooling
  (wiktextract) is separately licensed. Keep attribution with any redistribution.
- Expected location (either works):
  - next to the app executable: `kaikki.org-dictionary-English.jsonl`
  - or `resources/wiktionary/kaikki.org-dictionary-English.jsonl`

TypEng ships `resources/wiktionary/exam-pos-index.tsv`, a 14,942-candidate,
POS-only derivative of the Kaikki snapshot. It is used to validate normalized
parts of speech without requiring users to download the 3 GB export. It contains
no definitions or examples and remains subject to Wiktionary's CC-BY-SA 4.0 terms.
Entries without usable examples are not removed.

A step-by-step Chinese install guide is shipped with releases as
`词典安装指南.pdf` (source: `docs/dictionary_setup.zh-CN.md`).

---

# 数据来源

TypEng 可以使用多个第三方词典资源。每个资源都保留各自的许可证；在任何打包发行版中都请一并保留原始许可证声明。

## 界面字体

网站界面内置 Noto Sans SC 简体中文子集，使未安装中文字体的系统也能保持一致排版。

- 来源：https://fonts.google.com/noto/specimen/Noto+Sans+SC
- 打包来源：`@fontsource/noto-sans-sc`
- 许可证：SIL Open Font License 1.1（全文见 `static/fonts/OFL.txt`）

## ECDICT

TypEng 可以导入 ECDICT 的 `ecdict.csv` 来生成带标签的词库（四六级、考研、雅思等）。

- 来源：https://github.com/skywind3000/ECDICT
- 许可证：ECDICT 项目声明为 MIT License
- 使用字段：`word`、`phonetic`、`definition`、`translation`、`pos`、`tag`、`bnc`、`frq`

TypEng 会优先读取打包好的 `resources/ecdict.csv`。这是推荐的发行方式：用户点击预设词库按钮，TypEng 就用打包的 CSV 创建对应词库。

开发时如果没有 `resources/ecdict.csv`，TypEng 会依次尝试缓存的 `data/ecdict.csv`，再尝试从 ECDICT 在线下载。用户也可以在编辑界面提供本地的 `ecdict.csv` 文件。

## EFLLex

作为独立的 A1-C1 教材频率画像，用于词汇难度审计。原始 TSV 和衍生画像与 TypEng 的 MIT 代码分开授权。

- 来源：https://cental.uclouvain.be/cefrlex/efllex/download/
- 论文：Dürlich 与 François，*EFLLex: A Graded Lexical Resource for Learners of English as a Foreign Language*，LREC 2018
- 许可证：CC BY-NC-SA 4.0
- 存放位置：`resources/efllex/EFLLex.tsv`
- 处理：多词表达的下划线转为空格；临时审计等级取最早非零等级，同时完整保留各等级频率

## Wiktionary（Kaikki 提取版）

来自 Kaikki 的英文维基词典 JSONL 导出文件，提供按词性匹配的英文释义和例句。由于文件很大（约 3 GB），它**不**包含在发行包里；需要自动例句时请自行添加。

- 来源：https://kaikki.org/dictionary/English/
- 下载（直链）：https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl
  （文件名 `kaikki.org-dictionary-English.jsonl`，约 3 GB）
- 许可证：维基词典内容为 CC-BY-SA 4.0；Kaikki 的提取工具（wiktextract）单独授权。二次分发时请保留署名。
- 存放位置（任选其一）：
  - 放在应用可执行文件同级目录：`kaikki.org-dictionary-English.jsonl`
  - 或放在 `resources/wiktionary/kaikki.org-dictionary-English.jsonl`

发行包里附带了一份图文版中文安装指南 `词典安装指南.pdf`（源文件：`docs/dictionary_setup.zh-CN.md`）。
