# Bundled Resources

[简体中文](#打包资源)

Place release-bundled data files here. For an end-user, step-by-step Chinese
guide, see `词典安装指南.pdf` (shipped with releases) or
[docs/dictionary_setup.zh-CN.md](../docs/dictionary_setup.zh-CN.md).

## ECDICT

For packaged builds, put `ecdict.csv` in this directory:

```text
resources/ecdict.csv
```

TypEng uses this file first when a user clicks a preset library button such as CET4, CET6, IELTS, TOEFL, GRE, 高考, 中考, or 考研.

Source: https://github.com/skywind3000/ECDICT
License: MIT License, as stated by the ECDICT project.

Keep the original ECDICT license notice with packaged releases. The CSV is large, so decide intentionally whether to commit it to the repository or include it only in release packages.

## Open English WordNet

Powers the built-in "auto examples" feature. Release packages already include
this file (the release workflow downloads it), so no action is needed.

```text
resources/wordnet/english-wordnet-2025-json.zip
```

Source: https://github.com/globalwordnet/english-wordnet
Download: https://en-word.net/static/english-wordnet-2025-json.zip
License: CC-BY 4.0, as stated by the Open English WordNet project.

## Wiktionary (Kaikki)

Optional, but gives the richest example sentences. About 3 GB, so it is not
included in releases — users add it themselves. Put it here:

```text
resources/wiktionary/kaikki.org-dictionary-English.jsonl
```

(It also works if placed next to the app executable.)

Source / download: https://kaikki.org/dictionary/English/ ("Download JSON data for all senses")
License: Wiktionary content is CC-BY-SA 4.0; keep attribution with redistribution.

---

# 打包资源

发行版要打包的数据文件放在这个目录。面向普通用户的图文版中文安装指南见
`词典安装指南.pdf`（随发行包附带），或
[docs/dictionary_setup.zh-CN.md](../docs/dictionary_setup.zh-CN.md)。

## ECDICT

打包时把 `ecdict.csv` 放在此目录：

```text
resources/ecdict.csv
```

用户点击 CET4、CET6、IELTS、TOEFL、GRE、高考、中考、考研等预设词库按钮时，TypEng 会优先使用这个文件。

来源：https://github.com/skywind3000/ECDICT
许可证：ECDICT 项目声明为 MIT License。

请在打包发行版中保留 ECDICT 的原始许可证声明。CSV 文件较大，请自行决定是提交进仓库还是只放进发行包。

## Open English WordNet（英文词网）

驱动内置的「自动填充例句」功能。发行包已包含此文件（由发布流程自动下载），无需手动操作。

```text
resources/wordnet/english-wordnet-2025-json.zip
```

来源：https://github.com/globalwordnet/english-wordnet
下载：https://en-word.net/static/english-wordnet-2025-json.zip
许可证：Open English WordNet 项目声明为 CC-BY 4.0。

## Wiktionary（Kaikki 提取版）

可选，但能提供最丰富的例句。约 3 GB，因此不包含在发行包里，需用户自行添加。放在此处：

```text
resources/wiktionary/kaikki.org-dictionary-English.jsonl
```

（放在应用可执行文件同级目录也可以。）

来源 / 下载：https://kaikki.org/dictionary/English/ （点击 “Download JSON data for all senses”）
许可证：维基词典内容为 CC-BY-SA 4.0；二次分发时请保留署名。
