<div align="center">

# ⌨️ TypEng

**Type it. Don't just recognize it.**

A local-first English vocabulary trainer that builds real spelling muscle memory
through keyboard typing and in-context cloze practice.

<a href="https://github.com/Williamoel/typeng/releases/latest"><img src="https://img.shields.io/github/v/release/Williamoel/typeng?color=4c9a2a&label=release" alt="Latest release"></a>
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0a7bbb" alt="Platforms">
<img src="https://img.shields.io/badge/python-3.12-3776ab" alt="Python 3.12">
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
<img src="https://img.shields.io/badge/data-100%25%20local-e67e22" alt="Local-first">

**English** · [中文](README.zh-CN.md)

### [⬇️ Download the latest release](https://github.com/Williamoel/typeng/releases/latest)

Windows · macOS · Linux — download, unzip, double-click. No Python, no setup.

<br>

![Typing words](./images/typing_word.png)

</div>

## Why TypEng

Most vocabulary tools ask you to *recognize* a word or *pick* a meaning. That helps
you get familiar with meanings, but it doesn't prove you can actually spell the word,
and it rarely puts the word back into a real sentence.

TypEng makes you **type the answer** and **understand why the word fits the sentence**.
It breaks vocabulary learning into concrete actions: recall spelling from a Chinese
meaning or definition, type the word after hearing it, complete the word inside a real
cloze sentence, and consolidate it through wrong-word and spaced review.

Everything runs on your own machine — no account, no cloud, no telemetry. Use the
preset exam libraries, or import words from your classes, notebooks, and reading, and
write the example sentences you truly want to remember.

## Highlights

<table>
<tr>
<td width="50%">

### ⌨️ Type, don't guess
Recall spelling from meaning, definition, or audio, then type it out. Muscle memory,
not multiple choice.

</td>
<td width="50%">

### 📝 Cloze in context
The signature feature. Fill the word — or its correct inflected form — into a real
example sentence to train spelling, collocation, and word forms together.

</td>
</tr>
<tr>
<td width="50%">

### 📚 Your own libraries
Import TXT/CSV, split entries by part of speech, and exclude words you already know
from higher-level libraries to skip needless repetition.

</td>
<td width="50%">

### 🔁 Wrong-word + spaced review
An error notebook plus Ebbinghaus-inspired spaced review, with review targets you set
per library.

</td>
</tr>
<tr>
<td width="50%">

### 🔊 Optional pronunciation
US/UK audio via Youdao, with a browser speech-synthesis fallback. Turn it off to stay
fully offline.

</td>
<td width="50%">

### 🔒 Local-first
Your libraries, progress, and database never leave your computer. No account, no sync,
no tracking. (Pronunciation uses an optional online service; turn it off for fully
offline use.)

</td>
</tr>
</table>

## How TypEng works

**Rich practice cards.** Regular practice can show the Chinese meaning, part of speech,
phonetics, UK/US pronunciation, and English definition together. The same word is split
into separate entries per part of speech, so you learn each usage on its own — and the
POS-matched English definition helps advanced learners move beyond the Chinese meaning.
Misspell a word and TypEng shows the correct spelling immediately; after each group, it
re-runs the words you missed until every one is spelled correctly once.

![Mode choices](./images/mode_choice.png)

**You set the rhythm.** Choose how many entries to study next, and freely combine Chinese
prompts, English definitions, phonetics, automatic pronunciation, and cloze practice.
`With cloze` adds a contextual round after regular spelling; `Only in cloze` focuses on
context and falls back to normal spelling for entries without examples.

![Context practice](./images/filling_cloze.png)

**Cloze is the difference.** Instead of recalling a word from an isolated meaning, you
complete the target word or one of its forms inside a real sentence — training spelling,
collocation, and word forms in a way that's much closer to actual use.

![Import and exclusion](./images/import_and_exclude.png)

**Build libraries your way.** Import TXT/CSV per the format guide, and exclude overlapping
entries between libraries — for example, drop CET words you already know from a TOEFL list.
The editor also supports batch deletion for larger cleanups.

![Automatic filling](./images/auto_filling.png)

**Let TypEng do the busywork.** Give it just the words and it can auto-match example
sentences by part of speech. `Fill examples` picks the best-scoring sentence; `Refresh
examples` swaps in another from the top candidates; `Preview cleanup` flags entries that
still lack a reliable example. Missing Chinese meanings are filled from the local
dictionary by matching part of speech, and a bare word can be split into multiple entries
by its parts of speech.

![Review settings](./images/review_choice.png)

**Review that adapts.** Each library keeps independent study, wrong-word, and spaced-review
state. TypEng suggests reviews based on when each word was learned and the Ebbinghaus
forgetting curve, and you still control how many words to review and how many successful
rounds retire a word.

## The story behind TypEng

Since primary school I've used a program called Dr.eye, which helps you memorize words by typing them on a keyboard. It worked, but it only takes words and Chinese meanings — no context. Later I tried software with contextual spelling, but typing on a phone felt wrong and the word libraries were tiny. I wanted a tool that focused on desktop typing, where the muscle memory built through the keyboard could help me remember and *understand* words more deeply.

So TypEng is the tool I always wanted: use preset exam libraries directly, or import words from your classes, notebooks, and reading. Write the example sentences you truly want to remember, or let TypEng fill a reference context automatically and keep editing from there. It aims to be your own vocabulary training desk rather than another fixed word list.

## Feature Details

### Contextual learning and cloze practice

- Supports cloze practice based on example sentences.
- Users can manually add their own example sentences for words.
- If users do not have examples, TypEng can automatically match examples from local Wiktionary / WordNet resources.
- `With cloze` mode: normal spelling practice first, then cloze practice for words that have examples.
- `Only in cloze` mode: use cloze when an example exists; if no example exists, fall back to normal spelling practice.
- Cloze practice accepts both the entry's base word and the actual form in the sentence, and shows the correct sentence form when needed.

### Word-library customization

- Supports multiple local word libraries.
- Supports TXT and CSV word-list imports.
- Supports manually adding words and editing libraries.
- Supports user-defined Chinese meanings, parts of speech, and example sentences.
- Uses ECDICT tags to generate preset libraries such as CET4, CET6, IELTS, TOEFL, GRE, Gaokao, Zhongkao, and Kaoyan.
- Supports excluding overlapping words between libraries, which helps users remove already-mastered basic words from higher-level libraries.

### Parts of speech and definitions

- The same English word can be split into multiple entries by part of speech.
- Different parts of speech keep different Chinese meanings, English definitions, and examples.
- This is useful for training less familiar meanings of familiar words, where a common word may have very different uses as a noun, verb, adjective, or adverb.
- English definitions can be shown optionally, and TypEng tries to fill them according to the corresponding part of speech.
- Phonetics can be shown optionally, so they do not interfere with users who want to train listening vocabulary.

### Practice and review

- Study proceeds in order instead of random order.
- Supports Chinese prompt, audio-only, Chinese plus audio, and related modes.
- Pronunciation is played through Youdao Dictionary's audio interface, with US/UK options, and TypEng tries to fall back to browser speech synthesis when the audio is unavailable.
- Wrong-word book supports daily review. A word is moved back to learned after being answered correctly for the user-configured number of times.
- Learned words support spaced review inspired by the Ebbinghaus forgetting curve. Each library can set its own review target count.
- Before each review session, users can choose how many due words to review this time.
- The browser remembers practice options to reduce repeated setup.

## Dictionary and Example Sources

TypEng can run with only the user's own word lists, but local dictionary resources make it more complete.

### ECDICT

ECDICT is mainly used for:

- generating preset exam or category libraries
- Chinese meanings
- phonetics
- word frequency
- tags such as `cet4`, `cet6`, `toefl`, `ielts`, `gre`, `gk`, and `zk`

For packaging or local use, put the CSV file here:

```text
resources/ecdict.csv
```

Source: <https://github.com/skywind3000/ECDICT>  
License: the ECDICT project states that it uses the MIT License.

### Wiktionary / Kaikki

The English Wiktionary JSONL export from Kaikki is currently used as the main source for:

- POS-matched English definitions
- POS-matched English example sentences
- cloze examples

The file can be placed in the project root, or here:

```text
resources/wiktionary/kaikki.org-dictionary-English.jsonl
```

TypEng tries to filter out archaic, obsolete, dated, rare, inflection-only entries, and examples that are not suitable for learning.

### Open English WordNet

Open English WordNet is used as a fallback source for English definitions and examples.

Put the zip file here:

```text
resources/wordnet/english-wordnet-2025-json.zip
```

Source: <https://github.com/globalwordnet/english-wordnet>  
License: the Open English WordNet project states that it uses CC-BY 4.0.

### Youdao Dictionary audio interface

TypEng currently uses Youdao Dictionary's `dictvoice` audio interface for UK and US pronunciation, and tries to fall back to the browser's built-in speech synthesis when that interface is unavailable. When pronunciation is enabled, the browser requests the current practice word from Youdao's audio URL; if the app is used completely offline, automatic pronunciation may not be available.

## Privacy

TypEng is local-first: your word libraries, learning progress, and the SQLite
database never leave your computer, and there is no account system, telemetry,
or cloud sync.

The one exception is optional pronunciation. When audio playback is enabled,
the browser requests the current practice word from Youdao Dictionary's public
`dictvoice` audio endpoint, so that single word is sent to Youdao's servers. If
you prefer to stay fully offline, turn off automatic pronunciation in the
practice options; TypEng then falls back to the browser's built-in speech
synthesis, which does not make network requests.

## Download and Run

TypEng ships as a self-contained local zip for each platform. You do not need
to install Python, enter WSL, create a virtual environment, or type any Flask
commands. Download, extract, and run — the app starts a local server and opens
in your browser automatically. All data (SQLite database, dictionary resources,
learning records) stays on your computer.

Get the latest packages from the releases page:

**<https://github.com/Williamoel/typeng/releases/latest>**

### Windows

1. Download `typeng-v0.1.0-windows-x64.zip`.
2. Extract the whole folder.
3. Double-click `typeng.exe`.
4. The first time, Windows SmartScreen may warn about an unrecognized app
   (TypEng is not code-signed yet). Click **More info → Run anyway**.

### macOS

1. Download `typeng-v0.1.0-macos-arm64.zip` (Apple Silicon: M1/M2/M3) or
   `typeng-v0.1.0-macos-x64.zip` (Intel).
2. Extract the folder, then run `TypEng` inside it.
3. Because the app is unsigned, macOS Gatekeeper may block it on first launch.
   Right-click `TypEng` and choose **Open**, or run once in Terminal:

   ```bash
   xattr -dr com.apple.quarantine <extracted-folder>
   ```

### Linux

1. Download `typeng-v0.1.0-linux-x64.zip`.
2. Extract the folder, then run `./typeng` inside it.

### Optional dictionary resources

Released packages include empty `resources/` folders but not the large
dictionary files (ECDICT, Wiktionary, WordNet), which are big and carry their
own licenses. To enable preset exam libraries, English definitions, and example
sentences, drop those files into the extracted `resources/` folder as described
in [resources/README.md](resources/README.md) and [SOURCES.md](SOURCES.md).

Maintainers who want to build the packages themselves can follow
[PACKAGING.md](PACKAGING.md).

## Run from source (for developers)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`. This is a local Flask app — `127.0.0.1`
does not require a VPN or internet connection.

To test the desktop-style launcher: `python run_typeng.py`

## Import Format

TypEng supports TXT and CSV imports.

In the `Add Words` section of the editing interface, users can also enter only a word, or enter a word plus a part of speech. As long as local ECDICT resources are available, TypEng will try to automatically fill the Chinese meaning for the corresponding part of speech. If only a word is entered, TypEng will split it into multiple entries according to the parts of speech found in ECDICT. `Add Words` does not overwrite existing entries with the same word and the same part of speech. To modify existing entries, edit them directly in the library editing list. File imports are still recommended to use the standard format below.

Required fields:

- `word`
- `part_of_speech`
- `meaning`

Optional fields:

- `example_sentence`

TXT files can use tabs, commas, or vertical bars as separators:

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

They can also omit the header and use the same column order directly.

The same English word can appear multiple times because of different parts of speech. The same word plus the same part of speech is treated as the same entry.

## Practice Rules

- Submit an answer by pressing Enter or clicking the button.
- Leading and trailing spaces are ignored.
- Case is strict.
- Normal word practice requires typing the standard word stored in the entry.
- Cloze practice accepts both the entry's base word and the actual form in the sentence. If the user types the base word while the sentence uses an inflected form, TypEng marks it correct and shows the correct sentence form before moving to the next question.
- Wrong answers show the correct answer in red.
- In normal study, words that were typed incorrectly appear again until every word in the current group has been typed correctly once. At the end, users can choose which missed words should enter the wrong-word book.

## Review Mechanism

Each library has its own independent learning state.

Word statuses:

- `new`: not learned yet
- `learned`: completed normal study, or moved out of wrong-word review
- `wrong`: currently in the wrong-word book

Learned words can enter spaced review inspired by the Ebbinghaus forgetting curve. The current implementation uses a fixed interval table to schedule review dates: day 1, 2, 4, 7, 15, 30, 60, 120, 180, and 365. After each correct learned-word review, the word moves to the next interval. If it is answered incorrectly, it continues to appear in the current review session until it is answered correctly. After reaching the target count configured for that library, the word is no longer scheduled for learned-word review.

Each library can independently set the learned-word review target count, with a minimum of three successful reviews and a maximum of ten successful reviews. Before review starts, TypEng tells users how many words are currently due, and users can choose how many to review first according to their available time.

Wrong words are reviewed daily. If a wrong word is answered correctly but has not reached the target count yet, it stays in the wrong-word book and is scheduled for review the next day. If it is answered incorrectly, its accumulated correct count is reset to 0, and it is also scheduled for the next day. After a wrong word reaches the user-configured accumulated correct count, it moves back to learned words and enters learned-word spaced review starting from the next day.

## Project Structure

```text
app.py                 Flask application and core logic
templates/             Jinja templates
static/                CSS and browser JavaScript
data/                  local SQLite database and generated caches
resources/             optional local dictionary resources
samples/               sample import files
```

## Development Status

TypEng is an actively maintained open-source project. Multi-platform desktop packages
(Windows, macOS, Linux) are built and released automatically via GitHub Actions.
v0.1.2 as of July 2026.

Areas being worked on:

- import/export of learning progress
- better example-sentence quality scoring and ML-based ranking
- more accurate dictionary sense matching
- integration-test coverage beyond the existing unit + engine suites
- optional interface language switching

## Roadmap

Near term:

- continue improving automatic example selection
- ML-based example quality ranking
- improve Wiktionary English definition matching
- add import/export for libraries and learning progress

Long term:

- richer statistics
- better audio source management
- optional online dictionary lookup
- more built-in libraries with clear licenses

## Acknowledgements

The biggest inspiration for this project is [Dr.eye](https://www.dreye.com/). I have used it for almost fifteen years. Without it, I would not have known that words can be memorized through muscle memory, and a large part of my vocabulary accumulation came from it. I also want to thank [词达人](https://www.unipus.cn/) for the inspiration behind contextual fill-in-the-blank practice.

[Qwerty Learner](https://qwerty.kaiyi.cool/) is a vocabulary memorization and English muscle-memory training tool designed for keyboard workers. I only learned about it after I already had the rough idea for TypEng, but I found it unfortunate that it does not include contextual practice. During development, Qwerty Learner also gave me useful inspiration for solving the word-audio problem. Its open-source repository is [RealKai42/qwerty-learner](https://github.com/RealKai42/qwerty-learner).

## License

TypEng is released under the MIT License. See [LICENSE](LICENSE).

Dictionary and word-library resources keep their own licenses. See [SOURCES.md](SOURCES.md) and [resources/README.md](resources/README.md).
