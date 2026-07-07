# Bundled Resources

Place release-bundled data files here.

## ECDICT

For packaged builds, put `ecdict.csv` in this directory:

```text
resources/ecdict.csv
```

typeng uses this file first when a user clicks a preset library button such as CET4, CET6, IELTS, TOEFL, GRE, 高考, 中考, or 考研.

Source: https://github.com/skywind3000/ECDICT
License: MIT License, as stated by the ECDICT project.

Keep the original ECDICT license notice with packaged releases. The CSV is large, so decide intentionally whether to commit it to the repository or include it only in release packages.

## Open English WordNet

For English-only example fallback, put this file in `resources/wordnet/`:

```text
english-wordnet-2025-json.zip
```

Source: https://github.com/globalwordnet/english-wordnet
License: CC-BY 4.0, as stated by the Open English WordNet project.
