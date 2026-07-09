# Data Sources

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
