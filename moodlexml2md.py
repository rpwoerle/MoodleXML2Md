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
from pathlib import Path
from typing import List, Dict
import html


def clean_html(text: str) -> str:
    """Remove HTML tags and CDATA, decode HTML entities."""
    if not text:
        return ""
    
    # Remove CDATA wrapper
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    
    # Remove HTML tags but keep the content
    text = re.sub(r'<p>(.*?)</p>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Clean up whitespace
    text = text.strip()
    
    return text


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
    # Get text content, which might be None
    text = text_elem.text if text_elem.text is not None else ""
    return clean_html(text)


def convert_multichoice(question) -> str:
    """Convert a multiple choice question to Markdown."""
    name = get_element_text(question, 'name')
    question_text = get_element_text(question, 'questiontext')
    
    # Get default grade to display in header if not 1.0 or 4.0
    grade_elem = question.find('defaultgrade')
    grade = float(grade_elem.text) if grade_elem is not None and grade_elem.text else 1.0
    
    # Build header
    header = f"## Multi-choice: {name or question_text}"
    # Show grade only for values 1, 2, 3, 4
    if grade in [1.0, 2.0, 3.0, 4.0]:
        header += f" [{int(grade)}]"
    
    lines = [header]
    
    # Process answers
    for answer in question.findall('answer'):
        fraction = float(answer.get('fraction', 0))
        # Get text directly from answer element
        text_elem = answer.find('text')
        if text_elem is not None:
            answer_text = clean_html(text_elem.text if text_elem.text else "")
            if answer_text:
                # Mark correct answers with asterisk
                marker = "*" if fraction > 0 else ""
                lines.append(f"- {answer_text}{marker}")
    
    lines.append("")  # Empty line after question
    
    return "\n".join(lines)


def convert_cloze(question) -> str:
    """Convert a cloze (fill-in-the-blank) question to Markdown."""
    name = get_element_text(question, 'name')
    question_text = get_element_text(question, 'questiontext')
    
    # Convert cloze format from Moodle to simplified Markdown
    # Pattern: {1:SHORTANSWER:~=answer1~=answer2} -> {answer1|answer2}
    # Remove point values and question type
    def simplify_cloze(match):
        content = match.group(1)
        # Extract answers after ~=
        answers = re.findall(r'~=([^~}]+)', content)
        if answers:
            # Check if there's a point value
            point_match = re.match(r'(\d+):', content)
            if point_match and point_match.group(1) != '1':
                return '{' + point_match.group(1) + ':' + '|'.join(answers) + '}'
            return '{' + '|'.join(answers) + '}'
        return match.group(0)
    
    question_text = re.sub(r'\{([^}]+)\}', simplify_cloze, question_text)
    
    lines = [
        f"## Cloze: {name}",
        question_text,
        ""
    ]
    
    return "\n".join(lines)


def convert_matching(question) -> str:
    """Convert a matching question to Markdown."""
    name = get_element_text(question, 'name')
    question_text = get_element_text(question, 'questiontext')
    
    # Get default grade to display in header
    grade_elem = question.find('defaultgrade')
    grade = float(grade_elem.text) if grade_elem is not None and grade_elem.text else 1.0
    
    # Build header
    header = f"## Matching: {name or question_text}"
    # Show grade only for values 1, 2, 3, 4
    if grade in [1.0, 2.0, 3.0, 4.0]:
        header += f" [{int(grade)}]"
    
    lines = [header]
    
    # Process subquestions (pairs)
    for subquestion in question.findall('subquestion'):
        # Get question part from text element
        text_elem = subquestion.find('text')
        question_part = clean_html(text_elem.text if text_elem is not None and text_elem.text else "")
        
        # Get answer part
        answer_elem = subquestion.find('answer/text')
        answer_part = answer_elem.text if answer_elem is not None and answer_elem.text else ""
        
        if question_part and answer_part:
            lines.append(f"- {question_part} = {answer_part}")
    
    lines.append("")  # Empty line after question
    
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
