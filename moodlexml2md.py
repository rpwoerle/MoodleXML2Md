#!/usr/bin/env python3
"""
Moodle XML to Markdown Converter

Converts Moodle XML quiz files to Markdown format.
Supports multiple file conversion using wildcards or folder paths.
"""

import xml.etree.ElementTree as ET
import argparse
import sys
import re
import math
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Optional, Tuple


class _HTMLToMarkdown(HTMLParser):
    """Convert the HTML subset used in Moodle question text to Markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.table_rows: Optional[List[List[str]]] = None
        self.table_row: Optional[List[str]] = None
        self.table_cell: Optional[List[str]] = None
        self.lists: List[Tuple[str, int]] = []
        self.links: List[str] = []

    def _append(self, text: str) -> None:
        if self.table_cell is not None:
            self.table_cell.append(text)
        else:
            self.parts.append(text)

    def _block_break(self) -> None:
        current = "".join(self.parts)
        trailing_newlines = len(current) - len(current.rstrip("\n"))
        if trailing_newlines < 2:
            self.parts.append("\n" * (2 - trailing_newlines))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self._block_break()
            self.table_rows = []
        elif tag == "tr" and self.table_rows is not None:
            self.table_row = []
        elif tag in ("th", "td") and self.table_row is not None:
            self.table_cell = []
        elif tag in ("p", "div", "section", "article", "blockquote") or re.fullmatch(r"h[1-6]", tag):
            if not self.lists:
                self._block_break()
        elif tag in ("ul", "ol"):
            if not self.lists:
                self._block_break()
            self.lists.append((tag, 0))
        elif tag == "li":
            if self.parts and not self.parts[-1].endswith("\n"):
                self._append("\n")
            indent = "  " * max(0, len(self.lists) - 1)
            if self.lists and self.lists[-1][0] == "ol":
                kind, number = self.lists[-1]
                number += 1
                self.lists[-1] = (kind, number)
                marker = f"{number}. "
            else:
                marker = "- "
            self._append(indent + marker)
        elif tag in ("strong", "b"):
            self._append("**")
        elif tag in ("em", "i"):
            self._append("_")
        elif tag in ("del", "s", "strike"):
            self._append("~~")
        elif tag == "code":
            self._append("`")
        elif tag == "sub":
            self._append("~")
        elif tag == "sup":
            self._append("^")
        elif tag == "a":
            href = attributes.get("href") or ""
            self.links.append(href)
            if href:
                self._append("[")
        elif tag == "br":
            self._append("\n")
        elif tag == "img":
            source = attributes.get("src")
            if source:
                self._append(f"![{attributes.get('alt') or ''}]({source})")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.table_rows is not None:
            if self.table_row is not None:
                self.table_rows.append(self.table_row)
                self.table_row = None
            if self.table_rows:
                rows = self.table_rows
                width = max(len(row) for row in rows)

                def render_row(cells: List[str]) -> str:
                    values = [cell.strip().replace("|", r"\|") for cell in cells]
                    values.extend([""] * (width - len(values)))
                    return "| " + " | ".join(values) + " |"

                self.parts.append(render_row(rows[0]) + "\n")
                self.parts.append("| " + " | ".join("---" for _ in range(width)) + " |\n")
                self.parts.extend(render_row(row) + "\n" for row in rows[1:])
            self.table_rows = None
            self._block_break()
        elif tag == "tr" and self.table_rows is not None and self.table_row is not None:
            self.table_rows.append(self.table_row)
            self.table_row = None
        elif tag in ("th", "td") and self.table_cell is not None:
            self.table_row.append("".join(self.table_cell))
            self.table_cell = None
        elif tag in ("p", "div", "section", "article", "blockquote") or re.fullmatch(r"h[1-6]", tag):
            if not self.lists:
                self._block_break()
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self._block_break()
        elif tag == "li":
            self._append("\n")
        elif tag in ("strong", "b"):
            self._append("**")
        elif tag in ("em", "i"):
            self._append("_")
        elif tag in ("del", "s", "strike"):
            self._append("~~")
        elif tag == "code":
            self._append("`")
        elif tag == "sub":
            self._append("~")
        elif tag == "sup":
            self._append("^")
        elif tag == "a" and self.links:
            href = self.links.pop()
            if href:
                self._append(f"]({href})")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if data.isspace():
            if self.table_cell is None and "\n" in data:
                return
            data = " "
        else:
            data = re.sub(r"[ \t\r\f\v]+", " ", data)
        self._append(data)


def clean_html(text: str) -> str:
    """Convert Moodle HTML or plain text to Markdown and decode HTML entities."""
    if not text:
        return ""

    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    parser = _HTMLToMarkdown()
    parser.feed(text)
    parser.close()
    markdown = "\n".join(line.rstrip() for line in "".join(parser.parts).splitlines())
    markdown = re.sub(r"\\\((.*?)\\\)", lambda match: f"${match.group(1)}$", markdown, flags=re.DOTALL)
    markdown = re.sub(r"\\\[(.*?)\\\]", lambda match: f"$${match.group(1)}$$", markdown, flags=re.DOTALL)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"\n\n(?=\|)", "\n", markdown)
    return markdown.strip()


def get_element_text(element, tag: str, default: str = "") -> str:
    """Safely extract text from XML element."""
    if element is None:
        return default
    child = element.find(tag)
    if child is None:
        return default
    text_elem = child.find('text')
    if text_elem is None:
        return default
    return clean_html("".join(text_elem.itertext()))


def get_text(element, path: str, default: str = "") -> str:
    """Safely extract and convert the text of an XML element."""
    child = element.find(path) if element is not None else None
    if child is None:
        return default
    return clean_html("".join(child.itertext()))


def question_text_parts(question) -> Tuple[str, str, str]:
    """Return a leading HTML heading, the remaining body, and all question text."""
    text_element = question.find("questiontext/text")
    if text_element is None:
        return "", "", ""

    raw_text = "".join(text_element.itertext())
    full_text = clean_html(raw_text)
    heading = re.match(
        r"\s*<h[1-6]\b[^>]*>(.*?)</h[1-6]\s*>",
        raw_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if heading is None:
        return "", full_text, full_text

    return clean_html(heading.group(1)), clean_html(raw_text[heading.end():]), full_text


def question_grade(question) -> Optional[float]:
    grade = question.findtext("defaultgrade")
    return float(grade) if grade and grade.strip() else None


def question_header(question, label: str, include_question_text: bool = True) -> str:
    name = get_element_text(question, "name")
    heading, _, full_text = question_text_parts(question)
    question_text = (heading or full_text) if include_question_text else ""
    title = question_text or name
    header = f"## {label}: {title}"
    if question_text and name and name != question_text:
        header += f"||{name}"
    grade = question_grade(question)
    if grade is not None:
        header += f" [{grade:g}]"
    return header


def format_percentage(fraction: float) -> str:
    if math.isclose(fraction * 3, round(fraction * 3), abs_tol=0.001):
        return str(round(fraction))
    return f"{fraction:.6g}"


def uses_standard_multichoice_scoring(fractions: List[float]) -> bool:
    correct = [fraction for fraction in fractions if fraction > 0]
    incorrect = [fraction for fraction in fractions if fraction <= 0]
    if not correct:
        return False
    correct_fraction = 100 / len(correct)
    if not all(math.isclose(fraction, correct_fraction, abs_tol=0.01) for fraction in correct):
        return False
    if not incorrect:
        return True
    incorrect_fraction = -100 / len(incorrect)
    return all(math.isclose(fraction, incorrect_fraction, abs_tol=0.01) for fraction in incorrect)


def convert_multichoice(question) -> str:
    """Convert a Moodle single- or multiple-choice question to Markdown."""
    answers = question.findall("answer")
    fractions = [float(answer.get("fraction", 0)) for answer in answers]
    single_choice = question.findtext("single", "").strip().lower() == "true"
    label = "Single-Choice" if single_choice else "Multi-choice"
    lines = [question_header(question, label)]
    heading, body, _ = question_text_parts(question)
    if heading and body:
        lines.extend([body, ""])

    standard_scoring = not single_choice and uses_standard_multichoice_scoring(fractions)
    for answer, fraction in zip(answers, fractions):
        answer_text = get_text(answer, "text")
        if not answer_text:
            continue
        if single_choice:
            lines.append(f"- {answer_text} [{format_percentage(fraction)}%]")
        elif standard_scoring:
            lines.append(f"- {answer_text}{'*' if fraction > 0 else ''}")
        else:
            lines.append(f"- {answer_text} [{format_percentage(fraction)}%]")

    lines.append("")
    return "\n".join(lines)


def convert_cloze(question) -> str:
    """Convert a cloze (fill-in-the-blank) question to Markdown."""
    heading, body, full_text = question_text_parts(question)
    question_text = body if heading else full_text
    
    # Convert cloze format from Moodle to simplified Markdown
    # Pattern: {1:SHORTANSWER:~=answer1~=answer2} -> {answer1|answer2}
    # Remove point values and question type
    def simplify_cloze(match):
        content = match.group(1)
        # Extract answers after ~=
        answers = re.findall(r'~=([^~}]+)', content)
        if answers:
            # Check if there's a point value
            point_match = re.match(r'(\d+(?:\.\d+)?):', content)
            if point_match:
                return '{' + point_match.group(1) + ':' + '|'.join(answers) + '}'
            return '{' + '|'.join(answers) + '}'
        return match.group(0)
    
    question_text = re.sub(r'\{([^}]+)\}', simplify_cloze, question_text)
    
    lines = [question_header(question, "Cloze", include_question_text=bool(heading)), question_text, ""]
    
    return "\n".join(lines)


def convert_matching(question) -> str:
    """Convert a matching question to Markdown."""
    lines = [question_header(question, "Matching")]
    heading, body, _ = question_text_parts(question)
    if heading and body:
        lines.extend([body, ""])

    for subquestion in question.findall("subquestion"):
        question_part = get_text(subquestion, "text")
        answer_part = get_text(subquestion, "answer/text")
        if question_part or answer_part:
            left = f"{question_part} " if question_part else ""
            lines.append(f"- {left}= {answer_part}")

    lines.append("")
    return "\n".join(lines)


def convert_essay(question) -> str:
    """Convert an essay question and its grader guidance to Markdown."""
    heading, body, full_text = question_text_parts(question)
    lines = [question_header(question, "Essay", include_question_text=bool(heading))]
    question_body = body if heading else full_text
    if question_body:
        lines.append(question_body)
    graderinfo = get_text(question, "graderinfo")
    if graderinfo:
        lines.append(f"{{{graderinfo}}}")
    lines.append("")
    return "\n".join(lines)


def convert_aitext(question) -> str:
    """Convert an AI-text question and its grading information to Markdown."""
    heading, body, full_text = question_text_parts(question)
    lines = [question_header(question, "AI-Text", include_question_text=bool(heading))]
    question_body = body if heading else full_text
    if question_body:
        lines.append(question_body)

    aiprompt = get_text(question, "aiprompt")
    markscheme = get_text(question, "markscheme")
    if aiprompt:
        lines.append(f"{{AI-Prompt: {aiprompt}}}")
    if markscheme:
        lines.append(f"{{MarkScheme: {markscheme}}}")
    lines.append("")
    return "\n".join(lines)


def convert_drag_drop_image(question) -> str:
    """Convert an image drag-and-drop question to Markdown."""
    lines = [question_header(question, "Drag-Drop-Image")]
    heading, body, _ = question_text_parts(question)
    if heading and body:
        lines.extend([body, ""])

    image = question.find("file")
    if image is None or not image.get("name"):
        raise ValueError("Drag-Drop-Image question is missing an image file")

    drags = question.findall("drag")
    drags.sort(key=lambda drag: int(drag.findtext("no", "0") or "0"))
    drag_texts = [get_text(drag, "text") for drag in drags]
    if not drag_texts or any(not text for text in drag_texts):
        raise ValueError("Drag-Drop-Image question is missing draggable text")

    lines.extend(
        [
            f'image = "{image.get("name")}"',
            f"dropcount = {len(question.findall('drop'))}",
            f"dragtext = {';'.join(drag_texts)}",
            "",
        ]
    )
    return "\n".join(lines)


def convert_xml_to_md(xml_path: Path) -> str:
    """Convert a Moodle XML file to Markdown format."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        lines = ["# Quiz"]
        
        for question in root.findall('question'):
            qtype = question.get('type')
            
            if qtype == 'multichoice':
                lines.append(convert_multichoice(question))
            elif qtype == 'cloze':
                lines.append(convert_cloze(question))
            elif qtype == 'matching':
                lines.append(convert_matching(question))
            elif qtype == 'essay':
                lines.append(convert_essay(question))
            elif qtype == 'aitext':
                lines.append(convert_aitext(question))
            elif qtype == 'ddimageortext':
                lines.append(convert_drag_drop_image(question))
            else:
                # Skip unsupported question types
                print(f"Warning: Skipping unsupported question type '{qtype}'", file=sys.stderr)
        
        return "\n".join(lines)
    
    except ET.ParseError as e:
        print(f"Error parsing XML file {xml_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error processing file {xml_path}: {e}", file=sys.stderr)
        return None


def process_files(paths: List[str], output_dir: Path = None) -> int:
    """
    Process one or more XML files and convert them to Markdown.
    
    Args:
        paths: List of file paths, wildcards, or directories
        output_dir: Optional output directory (default: same as source)
    
    Returns:
        Number of successfully converted files
    """
    xml_files = []
    
    for path_str in paths:
        path = Path(path_str)
        
        # Handle directory
        if path.is_dir():
            xml_files.extend(path.glob('*.xml'))
        # Handle wildcards
        elif '*' in path_str or '?' in path_str:
            xml_files.extend(Path('.').glob(path_str))
        # Handle single file
        elif path.exists() and path.suffix.lower() == '.xml':
            xml_files.append(path)
        else:
            print(f"Warning: Skipping '{path_str}' - not found or not an XML file", file=sys.stderr)
    
    if not xml_files:
        print("Error: No XML files found to process", file=sys.stderr)
        return 0
    
    converted_count = 0
    
    for xml_file in xml_files:
        print(f"Converting: {xml_file}")
        
        markdown = convert_xml_to_md(xml_file)
        
        if markdown is not None:
            # Determine output path
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                md_file = output_dir / f"{xml_file.stem}.md"
            else:
                md_file = xml_file.with_suffix('.md')
            
            # Write Markdown file
            try:
                md_file.write_text(markdown, encoding='utf-8')
                print(f"  -> Created: {md_file}")
                converted_count += 1
            except Exception as e:
                print(f"Error writing file {md_file}: {e}", file=sys.stderr)
        else:
            print(f"  -> Failed to convert {xml_file}", file=sys.stderr)
    
    return converted_count


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Convert Moodle XML quiz files to Markdown format.',
        epilog='''
Examples:
  %(prog)s questions.xml                    # Convert single file
  %(prog)s *.xml                            # Convert all XML files in current directory
  %(prog)s quiz1.xml quiz2.xml              # Convert multiple files
  %(prog)s samples/                         # Convert all XML files in samples folder
  %(prog)s *.xml -o output/                 # Convert and save to output folder
        '''
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='XML file(s), wildcard pattern(s), or directory to convert'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output directory (default: same directory as source file)'
    )
    
    args = parser.parse_args()
    
    # Process files
    converted = process_files(args.files, args.output)
    
    print(f"\nConversion complete: {converted} file(s) converted successfully")
    
    return 0 if converted > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
