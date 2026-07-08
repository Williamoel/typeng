# typeng

Chinese users can refer to the Chinese README: [中文](README.zh-CN.md).

typeng is a local-first English vocabulary typing and memorization tool built with Python, Flask, SQLite, and a local web interface.

It is designed for English learners who want to memorize words through active typing and contextual understanding. typeng helps users build muscle memory for spelling by typing words on a keyboard, provides examples that are as complete as possible for users to fill in and use to understand context and usage, and offers review plans based on each user's personal choices.

## Some typeng design examples

![Typing words](./images/typing_word.png)

typeng's regular practice can show Chinese meanings, parts of speech, phonetics, UK/US pronunciation, and English definitions at the same time. The same word is split into more detailed entries by part of speech, so users can learn the meanings and usage of each part of speech separately. English definitions for the matching part of speech are especially useful for more advanced learners, because they help users move beyond Chinese meanings and understand the word's context more directly.

If a user misspells a word, typeng immediately shows the correct spelling. After the current group of new words ends, typeng asks the user to practice the missed words again until every word in the group has been spelled correctly once. Users can then decide which missed words should enter the wrong-word book for later review.

![Mode choices](./images/mode_choice.png)

typeng tries to leave the learning rhythm to the user. Users can choose how many entries to study next, and freely combine Chinese prompts, English definitions, phonetics, automatic pronunciation, and cloze practice.

Cloze is the most important difference in typeng. Many tools only let users quickly glance at example sentences, so learning often stays at the level of recognition. typeng removes the target word or its inflected form from an example sentence and asks the user to spell it in context. `With cloze` adds a round of contextual practice after regular spelling, while `Only in cloze` focuses on contextual practice and falls back to regular spelling for entries without examples.

![Context practice](./images/filling_cloze.png)

In cloze practice, users do not recall words from isolated meanings. They complete the target word or one of its forms inside a real sentence, which trains spelling, collocation, and word forms in a way that is closer to actual use.

![Import and exclusion](./images/import_and_exclude.png)

To help users build their own libraries, typeng supports TXT/CSV import according to the `Format Guide`, and it can exclude overlapping entries between local libraries. For example, if a user has already learned CET-level basic words, they can remove overlapping entries from a higher-level library such as TOEFL and avoid unnecessary repetition. The editing interface also supports batch deletion for larger cleanup work.

![Automatic filling](./images/auto_filling.png)

Many users may only want to provide the words first, so typeng provides automatic filling. Users can ask the system to match example sentences by part of speech within a selected range, and use `Preview cleanup` to check entries that still do not have reliable examples before deciding whether to keep them.

When a manually added word has no Chinese meaning, typeng tries to fill it from the local dictionary by matching the part of speech. If the user only enters the word, typeng can also split it into multiple entries according to the parts of speech found in the dictionary.

![Review settings](./images/review_choice.png)

Each library has independent study, wrong-word, and spaced-review states. typeng gives review suggestions according to when each word was learned and the Ebbinghaus forgetting curve, while users can still adjust how many words to review this time and how many successful review rounds a word needs before reminders stop.

## Why typeng

The starting point of this open-source project is that I have never found a tool that really lets me memorize vocabulary efficiently. Many mainstream vocabulary tools are more about "recognizing a word" or "choosing a meaning". These exercises can help users become familiar with meanings, but sometimes they cannot guarantee that users can really spell the word, and they do not necessarily help users put the word back into context.

Since primary school, I have used a program called Dr.eye, which helps memorize words by typing on a keyboard. But it only lets users provide words and Chinese meanings, and it does not provide context. Later, I also encountered software with contextual spelling, but typing on a phone did not work very well, and the available word libraries were very small. So I wanted this application to focus only on desktop users. I hope the muscle memory built through keyboard typing can help users remember and understand words more deeply.

typeng emphasizes making users actually type the answer and understand why the word can be used in a sentence. It breaks vocabulary learning into several more concrete actions: recalling spelling from Chinese or definitions, typing the word after hearing pronunciation, understanding usage through cloze examples, and repeatedly consolidating words through wrong-word review and learned-word review.

Compared with tools that only provide fixed word lists, typeng hopes to become the user's own vocabulary training desk. You can directly use preset exam libraries, or import words collected from classes, vocabulary notebooks, and reading materials. You can manually write the example sentences you truly want to remember, or let the system first fill a reference context automatically and then continue editing it.

At the moment, this project stays local-first:

- no account system
- no cloud sync
- local SQLite database
- runs on the user's own computer
- can use local dictionary resources to generate preset libraries, English definitions, and example sentences

## Feature Details

### Contextual learning and cloze practice

- Supports cloze practice based on example sentences.
- Users can manually add their own example sentences for words.
- If users do not have examples, typeng can automatically match examples from local Wiktionary / WordNet resources.
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
- English definitions can be shown optionally, and typeng tries to fill them according to the corresponding part of speech.
- Phonetics can be shown optionally, so they do not interfere with users who want to train listening vocabulary.

### Practice and review

- Study proceeds in order instead of random order.
- Supports Chinese prompt, audio-only, Chinese plus audio, and related modes.
- Pronunciation is played through Youdao Dictionary's audio interface, with US/UK options, and typeng tries to fall back to browser speech synthesis when the audio is unavailable.
- Wrong-word book supports daily review. A word is moved back to learned after being answered correctly for the user-configured number of times.
- Learned words support spaced review inspired by the Ebbinghaus forgetting curve. Each library can set its own review target count.
- Before each review session, users can choose how many due words to review this time.
- The browser remembers practice options to reduce repeated setup.

## Dictionary and Example Sources

typeng can run with only the user's own word lists, but local dictionary resources make it more complete.

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

typeng tries to filter out archaic, obsolete, dated, rare, inflection-only entries, and examples that are not suitable for learning.

### Open English WordNet

Open English WordNet is used as a fallback source for English definitions and examples.

Put the zip file here:

```text
resources/wordnet/english-wordnet-2025-json.zip
```

Source: <https://github.com/globalwordnet/english-wordnet>  
License: the Open English WordNet project states that it uses CC-BY 4.0.

### Youdao Dictionary audio interface

typeng currently uses Youdao Dictionary's `dictvoice` audio interface for UK and US pronunciation, and tries to fall back to the browser's built-in speech synthesis when that interface is unavailable. This feature requires the browser to be able to access the corresponding Youdao audio URL; if the app is used completely offline, automatic pronunciation may not be available.

## Run Locally

The current version is mainly for development and testing. Run it as follows:

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

This is a local Flask web application. Opening `127.0.0.1` does not require a VPN or an internet connection.

## Distribution Plan

typeng's target distribution format is a local zip package for ordinary Windows users:

1. Download the typeng zip package.
2. Extract it to a local folder.
3. Double-click `typeng.exe`.
4. The program starts the local service automatically and opens typeng in the browser.

In this workflow, users do not need to manually enter WSL, create a virtual environment, or type Flask startup commands. The SQLite database, dictionary resources, and learning records are all kept locally. The current repository has not finished desktop packaging yet; this will be a later release goal.

The planned Windows packaging workflow, resource layout, and pre-release checklist are documented in [PACKAGING.md](PACKAGING.md).

## Import Format

typeng supports TXT and CSV imports.

In the `Add Words` section of the editing interface, users can also enter only a word, or enter a word plus a part of speech. As long as local ECDICT resources are available, typeng will try to automatically fill the Chinese meaning for the corresponding part of speech. If only a word is entered, typeng will split it into multiple entries according to the parts of speech found in ECDICT. `Add Words` does not overwrite existing entries with the same word and the same part of speech. To modify existing entries, edit them directly in the library editing list. File imports are still recommended to use the standard format below.

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
- Cloze practice accepts both the entry's base word and the actual form in the sentence. If the user types the base word while the sentence uses an inflected form, typeng marks it correct and shows the correct sentence form before moving to the next question.
- Wrong answers show the correct answer in red.
- In normal study, words that were typed incorrectly appear again until every word in the current group has been typed correctly once. At the end, users can choose which missed words should enter the wrong-word book.

## Review Mechanism

Each library has its own independent learning state.

Word statuses:

- `new`: not learned yet
- `learned`: completed normal study, or moved out of wrong-word review
- `wrong`: currently in the wrong-word book

Learned words can enter spaced review inspired by the Ebbinghaus forgetting curve. The current implementation uses a fixed interval table to schedule review dates: day 1, 2, 4, 7, 15, 30, 60, 120, 180, and 365. After each correct learned-word review, the word moves to the next interval. If it is answered incorrectly, it continues to appear in the current review session until it is answered correctly. After reaching the target count configured for that library, the word is no longer scheduled for learned-word review.

Each library can independently set the learned-word review target count, with a minimum of three successful reviews and a maximum of ten successful reviews. Before review starts, typeng tells users how many words are currently due, and users can choose how many to review first according to their available time.

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

typeng is currently a student-scale local application, not a fully packaged desktop program for ordinary users yet. The current goal is to first build a usable, understandable Python project that can keep expanding, then gradually improve packaging, testing, and release workflow.

Areas that still need improvement:

- packaging for non-technical users
- import/export of learning progress
- better example-sentence quality scoring
- more accurate dictionary sense matching
- more complete documentation and tests
- optional interface language switching

## Roadmap

Near term:

- continue improving automatic example selection
- improve Wiktionary English definition matching
- add import/export for libraries and learning progress
- add tests for review scheduling and cloze behavior

Long term:

- desktop packaging
- richer statistics
- better audio source management
- optional online dictionary lookup
- more built-in libraries with clear licenses

## Acknowledgements

The biggest inspiration for this project is [Dr.eye](https://www.dreye.com/). I have used it for almost fifteen years. Without it, I would not have known that words can be memorized through muscle memory, and a large part of my vocabulary accumulation came from it. I also want to thank [词达人](https://www.unipus.cn/) for the inspiration behind contextual fill-in-the-blank practice.

[Qwerty Learner](https://qwerty.kaiyi.cool/) is a vocabulary memorization and English muscle-memory training tool designed for keyboard workers. I only learned about it after I already had the rough idea for typeng, but I found it unfortunate that it does not include contextual practice. During development, Qwerty Learner also gave me useful inspiration for solving the word-audio problem. Its open-source repository is [RealKai42/qwerty-learner](https://github.com/RealKai42/qwerty-learner).

## License

Project license: to be decided.

Dictionary and word-library resources keep their own licenses. See [SOURCES.md](SOURCES.md) and [resources/README.md](resources/README.md).
