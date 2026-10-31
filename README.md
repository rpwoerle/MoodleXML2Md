# MoodleXML2Md
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

MoodleXML2Md converts Moodle quiz XML files into Markdown. It can convert one
file, several files, wildcard matches, or every XML file in a directory.

## Requirements

- Python 3.9 or later
- No third-party Python packages are required

## Usage

Run the converter from the project directory:

```bash
python moodlexml2md.py samples/questions.xml
```

Pass more than one file, a wildcard, or a directory to convert multiple files:

```bash
python moodlexml2md.py quiz1.xml quiz2.xml
python moodlexml2md.py "*.xml"
python moodlexml2md.py samples/
```

By default, each Markdown file is written beside its source XML file using the
same base name. Use `-o` or `--output` to choose an output directory:

```bash
python moodlexml2md.py "*.xml" --output converted/
```

The output directory is created if needed. Existing output files with the same
name are overwritten.

For command-line help:

```bash
python moodlexml2md.py --help
```

## Supported question types

The converter supports these Moodle question types:

- **Multiple choice** (`multichoice`): exported as `Single-Choice` or
  `Multi-choice`, based on Moodle's single-answer setting. Answers include
  their grading percentages; standard equal-weight multi-choice scoring is
  represented with `*` on correct answers.
- **Cloze** (`cloze`): the question text and gaps are converted to Markdown.
  Correct answers introduced by Moodle's `~=` syntax are joined with `|`.
  Point values are retained when present. If the question text starts with an
  HTML heading, that heading becomes the Markdown title and the Moodle question
  name follows it after `||`.
- **Matching** (`matching`): subquestions become `- prompt = answer` lines.
  Entries with no prompt are kept as distractor answers.
- **Essay** (`essay`): converts the question text and appends grader information
  in braces when present.
- **AI-Text** (`aitext`): converts the question text and includes the AI prompt
  and marking scheme when present.
- **Drag-Drop-Image** (`ddimageortext`): exports the question text, image name,
  drop count, and draggable labels.

Question headings use the form `## Type: title||name [points]`. Where a
question has a leading HTML heading, it is used as the title; otherwise the
Moodle question name is used. A differing Moodle name is included after `||`.
The points suffix is included when Moodle provides a default grade.

Question types not listed above are skipped with a warning.

## Text and formatting

Moodle question and answer HTML is converted to a Markdown subset. The
converter handles paragraphs and common block elements, headings, lists,
tables, links, images, bold and italic text, strikethrough, inline code,
subscripts and superscripts. Moodle inline and display math delimiters are
converted to `$...$` and `$$...$$`.

The conversion preserves text and common formatting, but does not preserve
arbitrary HTML, styling, or every Moodle-specific feature. Image references
are written as Markdown links to their source; the image files themselves are
not extracted.

## Development

The project is implemented in `moodlexml2md.py` using the Python standard
library. No package installation is needed. A development environment can be
created with:

```bash
python -m venv .venv
```

Activate the environment and run the converter or its help command as shown
above. `samples/questions.xml` and `samples/questions.md` provide a sample input
and its converted output; `samples_test/questions.md` is an additional
conversion example.

## Disclaimer

This project is provided "as is", without warranties of any kind, express or
implied. The developers and contributors are not liable for any damages,
losses, or other issues resulting from the use of this software.

The project was developed with substantial assistance from the GitHub Copilot
AI agent. Review the code and generated Markdown, and verify the results in
your own Moodle environment before relying on them.
