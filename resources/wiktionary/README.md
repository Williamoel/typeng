# Wiktionary exam POS index

`usage-patterns.tsv` is an audited supplement for fixed expressions present
in Wiktionary Usage notes but omitted from the Kaikki JSONL export. Rows keep
their source URL and are consumed only while building the local lookup cache;
the application never fetches them at request time.

`exam-pos-index.tsv` is a POS-presence-only derivative of the English Kaikki
Wiktionary JSONL snapshot. It covers the 14,942 words appearing in TypEng's
ECDICT exam candidates and contains no definitions or examples.

- Source: https://kaikki.org/dictionary/English/
- Source snapshot file: `kaikki.org-dictionary-English.jsonl`
- Local snapshot timestamp: 2026-07-06
- Source snapshot SHA-256: `e26c506f391af2cf8c13bc6feeeddcd47658c11034d3b8c40ced9de255b34830`
- License: CC-BY-SA 4.0
- Generated with: `scripts/build_wiktionary_exam_pos_index.py`
- Normalization: source POS labels are mapped into TypEng's canonical lexical groups
- SHA-256: `cdeac7779022786122f3dbd6b74722edb1afe2d671fff8b3e6142a7c6d665c0e`

An empty `parts` field means that the candidate lexeme was not found in this
snapshot. Example availability is deliberately not represented in this file.
