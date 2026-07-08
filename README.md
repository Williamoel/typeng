# typeng

Chinese users can refer to the Chinese README: [中文](README.zh-CN.md).

typeng is a local-first English vocabulary typing and memorization tool built with Python, Flask, SQLite, and a local web interface.

It is designed for English learners who want to memorize words through active typing and contextual understanding. typeng helps users build muscle memory for spelling by typing words on a keyboard, provides examples that are as complete as possible for users to fill in and use to understand context and usage, and offers review plans based on each user's personal choices.

## Some typeng design examples

![Typing words](./images/typing_word.png)

Like other typing-based vocabulary tools, typeng provides a regular mode with Chinese meanings, parts of speech, phonetics, automatic pronunciation with both UK and US audio, and English definitions. Words in the library are divided into more detailed entries by part of speech, so users can fully learn the meanings and usage of different parts of speech. We especially added English definitions for the corresponding part of speech, because advanced English learners should not be limited to memorizing Chinese meanings; they can further use English definitions to clarify the context of a word.

When a user misspells a word, typeng immediately shows the correct spelling. After the user finishes spelling all new words, typeng asks them to spell the previously missed words again until every word in the current group has been spelled correctly once. Misspelled words can then be added to the wrong-word book by the user's own choice for future review and consolidation.

![Mode choices](./images/mode_choice.png)

For word learning, typeng tries to give users as much personalization as possible. Users can freely choose how many entries to study next, and they can also choose modes to match their preferences.

The cloze mode is what makes typeng different from most vocabulary-learning tools. Most tools only let users quickly glance through example sentences, with the main focus still on memorizing words. Users often stop at the stage of recognition. typeng, however, removes the target word or its inflected form from an existing example and asks the user to spell it, so users can better understand the context, usage, and even inflected forms of the word. `With cloze` mode runs a round of contextual spelling practice after regular word spelling. `Only in cloze` mode only runs contextual spelling practice, while words without examples fall back to regular spelling.

![Context practice](./images/filling_cloze.png)

For every entry that has an example, cloze mode removes the target word or one of its forms from the example and asks the user to spell it correctly. This lets users learn usage and collocation in a real context instead of memorizing isolated meanings.

![Import and exclusion](./images/import_and_exclude.png)

To let users personalize their own libraries, typeng provides efficient import operations. Users can quickly build a library by importing TXT or CSV files in the formats allowed by the `Format Guide`.

Because the preset libraries contain many basic words, users can use overlap exclusion to remove words that are too easy or already learned in other libraries, which helps speed up learning. typeng also provides quick batch deletion for large numbers of entries.

![Automatic filling](./images/auto_filling.png)

Many users only want to provide the words they want to learn and do not want to fill in examples or even Chinese meanings themselves, so typeng provides automatic filling. For a selected range of words, clicking `Fill examples` makes typeng automatically match suitable dictionary examples according to each entry's part of speech. For the small number of words or parts of speech that cannot be matched with examples, users can click `Preview cleanup` to preview those entries and decide whether to keep them.

When users manually add words without entering Chinese meanings, typeng automatically looks up dictionary meanings that match the part of speech and fills them in. If no part of speech is provided, typeng creates multiple entries according to the parts of speech found in the dictionary.

![Review settings](./images/review_choice.png)

Each library has independent study, wrong-word, and spaced-review states. For learned words and wrong words, typeng gives review suggestions according to when each word was learned and the Ebbinghaus forgetting curve, while still allowing users to personalize the number of words to review and the number of review rounds they want.

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

The biggest inspiration for this project is Dr.eye. I have used it for almost fifteen years. Without it, I would not have known that words can be memorized through muscle memory, and a large part of my vocabulary accumulation came from it. I also want to thank 词达人 for the inspiration behind contextual fill-in-the-blank practice.

Querty Learner is a vocabulary memorization and English muscle-memory training tool designed for keyboard workers. I only learned about it after I already had the rough idea for typeng, but I found it unfortunate that it does not include contextual practice. During development, Querty Learner also gave me useful inspiration for solving the word-audio problem.

## License

Project license: to be decided.

Dictionary and word-library resources keep their own licenses. See [SOURCES.md](SOURCES.md) and [resources/README.md](resources/README.md).
