# typeng

[README](README.zh-CN.md)

typeng is a local-first English vocabulary typing trainer built with Python, Flask, SQLite, and a browser-based interface.

It is designed for learners who want to remember words through active typing and contextual understanding. typeng does not treat vocabulary learning as mechanical multiple choice practice. Its core idea is to combine spelling recall, contextual cloze practice, part-of-speech-aware word entries, user-owned libraries, and customizable review.

typeng's most important design points are:

- **Contextual cloze practice**: remove the target word from an example sentence so the learner recalls it inside real usage, not as an isolated translation.
- **Highly customizable libraries**: import TXT/CSV word lists, add words manually, and edit parts of speech, meanings, and examples.
- **Automatic learning material filling**: when the learner has not prepared examples, typeng can use local dictionary resources to fill POS-matched English definitions and example sentences.
- **Separate entries by part of speech**: the same spelling can become separate learning items for different parts of speech, which helps with familiar words used in less familiar senses.
- **Customizable review**: each library has independent study, wrong-word, and spaced-review state, with configurable review targets and session sizes; learned-word review follows the idea of Ebbinghaus-style spaced repetition.

## Why typeng

Many vocabulary tools ask learners to recognize a word or choose an option. That can help with familiarity, but it does not always prove that the learner can spell the word or use it in context.

typeng asks the learner to type the answer and understand why the word works in the sentence. It breaks vocabulary learning into several concrete actions: recall the spelling from a Chinese prompt or definition, type the word from audio, understand usage through cloze examples, and consolidate difficult words through wrong-word and learned-word review.

The goal is not to become a heavy learning platform. typeng aims to stay lightweight, local, and controllable enough for long-term personal word libraries and learning records.

Compared with tools that mainly provide fixed word lists, typeng is meant to become the learner's own vocabulary training desk. You can start from preset exam libraries, import words from classes, reading notes, or personal notebooks, write your own examples, or let the system fill a reference example first and edit it later.

The project is intentionally local-first:

- no account system
- no cloud sync
- local SQLite database
- runs on the user's own computer
- optional local dictionary resources for preset libraries, definitions, and example sentences

## Core Features

### Context And Cloze Practice

- Cloze practice based on example sentences.
- Users can manually add their own example sentences.
- If no example is available, typeng can automatically match examples from local Wiktionary / WordNet resources.
- "With cloze" mode: type words first, then complete cloze examples for words with examples.
- "Only in cloze" mode: use cloze when available and fall back to normal typing when no example exists.
- Cloze practice accepts both the base word and the actual sentence form, then shows the correct sentence form when needed.

### Custom Word Libraries

- Multiple local word libraries.
- TXT and CSV word-list import.
- Manual word adding and library editing.
- User-defined Chinese meanings, parts of speech, and example sentences.
- Built-in preset libraries from ECDICT tags, such as CET4, CET6, IELTS, TOEFL, GRE, 高考, 中考, and 考研.
- Library overlap exclusion, useful for removing already-mastered basic words from a higher-level library.

### Parts Of Speech And Definitions

- The same English spelling can be stored as separate entries for different parts of speech.
- Different parts of speech can keep different Chinese meanings, English definitions, and examples.
- This helps train familiar words in less familiar senses, such as common words that behave differently as nouns, verbs, adjectives, or adverbs.
- Optional English definition display, filled by matching the corresponding part of speech where possible.
- Optional phonetic display, so audio-focused practice can hide phonetics when they are distracting.

### Practice And Review

- Ordered study sessions instead of random order.
- Chinese prompt, audio-only, and Chinese-plus-audio practice modes.
- Local pronunciation playback with selectable US/UK accent.
- Wrong-word book with daily review; words move back to learned after the configured number of correct reviews.
- Learned-word spaced review inspired by the Ebbinghaus forgetting curve, with independent review targets per library.
- Review sessions can be limited by the learner's available time.
- Browser-local memory for practice display options.

## Dictionary And Example Sources

typeng can work with user-provided word lists only, but it becomes more useful when local dictionary resources are available.

### ECDICT

ECDICT is used for:

- preset exam/category libraries
- Chinese meanings
- phonetic symbols
- word frequency
- source tags such as `cet4`, `cet6`, `toefl`, `ielts`, `gre`, `gk`, and `zk`

Place the CSV here for packaged or local use:

```text
resources/ecdict.csv
```

Source: <https://github.com/skywind3000/ECDICT>  
License: MIT License, as stated by the ECDICT project.

### Wiktionary / Kaikki

The Kaikki English Wiktionary JSONL export is used as the primary source for:

- POS-matched English definitions
- POS-matched example sentences
- cloze examples

Put the file in the project root or:

```text
resources/wiktionary/kaikki.org-dictionary-English.jsonl
```

typeng filters out archaic, obsolete, dated, rare, form-of, and unsuitable examples where possible.

### Open English WordNet

Open English WordNet is used as a fallback source for English definitions and examples.

Put the zip file here:

```text
resources/wordnet/english-wordnet-2025-json.zip
```

Source: <https://github.com/globalwordnet/english-wordnet>  
License: CC-BY 4.0, as stated by the Open English WordNet project.

## Run Locally

The current version is mainly intended for development and testing:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The app is a local Flask web app. Opening `127.0.0.1` does not require a VPN or internet connection.

## Planned Distribution

The intended user-facing distribution is a local Windows zip package:

1. Download the typeng zip package.
2. Extract it to a local folder.
3. Double-click `typeng.exe`.
4. The app starts a local service and opens typeng in the browser automatically.

With this workflow, users would not need to enter WSL, create a virtual environment, or run Flask commands manually. The SQLite database, dictionary resources, and learning records would remain local. The current repository has not completed this desktop packaging step yet; it is a future release target.

See [PACKAGING.md](PACKAGING.md) for the planned PyInstaller-based Windows packaging workflow, resource layout, and release checklist.

## Import Format

typeng supports TXT and CSV imports.

In the `Add Words` panel, users can enter only a word, or a word plus part of speech. If local ECDICT data is available, typeng tries to fill the matching Chinese meaning automatically. When only the word is provided, typeng expands it into separate entries by ECDICT part of speech. `Add Words` does not overwrite an existing entry with the same word and part of speech; edit existing entries from the library table instead. File imports should still use the standard format below.

Required fields:

- `word`
- `part_of_speech`
- `meaning`

Optional field:

- `example_sentence`

TXT files can use tabs, commas, or pipes:

```text
abandon	verb	放弃；遗弃
ability	noun	能力
close	adjective	近的；亲密的
close	verb	关闭
abandon	verb	放弃；遗弃	The company decided to abandon the old plan.
```

CSV files can use a header:

```csv
word,part_of_speech,meaning,example_sentence
abandon,verb,放弃；遗弃,The company decided to abandon the old plan.
```

or the same columns without a header.

The same word can appear multiple times if the part of speech differs. The same word plus the same part of speech is treated as one entry.

## Practice Rules

- Answers are submitted by pressing Enter or the submit button.
- Leading and trailing spaces are ignored.
- Case is strict.
- Normal word practice expects the stored word.
- Cloze practice accepts both the base word and the sentence form. If the learner types the base word but the sentence uses an inflected form, typeng marks it correct and shows the correct sentence form before moving on.
- Wrong answers show the correct word in red.
- In normal study, missed words repeat until every word in the batch has been typed correctly once. At the end, the learner chooses which missed words should enter the wrong-word book.

## Review Behavior

Each library has its own learning state.

Word statuses:

- `new`: not learned yet
- `learned`: completed in normal study or cleared from wrong-word review
- `wrong`: currently in the wrong-word book

Learned words can enter spaced review inspired by the Ebbinghaus forgetting curve. The current implementation uses a fixed interval schedule: day 1, 2, 4, 7, 15, 30, 60, 120, 180, and 365. After each correct learned-word review, the word moves to the next interval. If the learner misses it, it keeps appearing in the current review session until answered correctly. Once it reaches the configured target for that library, typeng stops scheduling learned-word review for that word.

The learned-word review target can be configured per library, with a minimum of three successful reviews and a maximum of ten successful reviews. Before a review session starts, typeng shows how many words are due and lets the learner choose how many to review in the current session.

Wrong words are reviewed daily. If a wrong word is answered correctly but has not reached the target count yet, it stays in the wrong-word book and is scheduled for the next day. A wrong answer resets its wrong-word correct count to 0 and also schedules it for the next day. Once a wrong word reaches the configured cumulative correct count, it moves back to learned and starts learned-word spaced review from the next day.

## Project Structure

```text
app.py                 Flask app and core logic
templates/             Jinja templates
static/                CSS and browser JavaScript
data/                  local SQLite database and generated caches
resources/             optional bundled dictionary resources
samples/               sample import files
```

## Development Status

typeng is currently a student-scale local application, not a polished packaged desktop product. The first goal is a usable and understandable Python project that can run locally and be extended gradually; packaging, tests, and release workflow can be improved step by step.

Known areas for improvement:

- better packaging for non-technical users
- import/export of learning progress
- stronger example sentence quality scoring
- better dictionary sense matching
- more complete documentation and tests
- optional UI language switching

## Roadmap

Near-term:

- refine example sentence selection
- improve Wiktionary definition matching
- add import/export for libraries and progress
- add tests around review scheduling and cloze behavior

Longer-term:

- desktop packaging
- richer statistics
- better audio source management
- optional online dictionary lookup
- more curated built-in libraries with clear licenses

## License

Project license: to be decided.

Dictionary and vocabulary resources keep their own licenses. See [SOURCES.md](SOURCES.md) and [resources/README.md](resources/README.md).
