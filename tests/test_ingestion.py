"""Tests for markdown ingestion."""

from pathlib import Path

from texflow.ingestion import ingest_markdown, ingest_raw
from texflow.model import (
    CodeBlock,
    Document,
    Figure,
    ItemList,
    Paragraph,
    Section,
    Table,
)
from texflow.serializer import serialize

FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_raw_text():
    doc = ingest_raw("Hello world")
    assert len(doc.content) == 1
    assert isinstance(doc.content[0], Paragraph)
    assert doc.content[0].text == "Hello world"


def test_ingest_raw_empty():
    doc = ingest_raw("")
    assert doc.content == []


def test_ingest_frontmatter_metadata():
    md = """---
title: My Paper
author: Alice
date: 2026-01-01
abstract: A short abstract.
---

## Introduction

Some text.
"""
    doc = ingest_markdown(md)
    assert doc.metadata.title == "My Paper"
    assert doc.metadata.author == "Alice"
    assert doc.metadata.date == "2026-01-01"
    assert doc.metadata.abstract == "A short abstract."


def test_ingest_h1_as_title():
    md = "# My Title\n\nSome content."
    doc = ingest_markdown(md)
    assert doc.metadata.title == "My Title"


def test_ingest_sections():
    md = """## Introduction

First paragraph.

## Methods

Second paragraph.

### Data Collection

Details here.
"""
    doc = ingest_markdown(md)
    # Should have 2 top-level sections
    sections = [b for b in doc.content if isinstance(b, Section)]
    assert len(sections) == 2
    assert sections[0].title == "Introduction"
    assert sections[1].title == "Methods"
    # Methods should have a subsection
    subsections = [b for b in sections[1].content if isinstance(b, Section)]
    assert len(subsections) == 1
    assert subsections[0].title == "Data Collection"


def test_ingest_paragraph():
    md = "## Section\n\nThis is **bold** and *italic* with `code`."
    doc = ingest_markdown(md)
    sec = doc.content[0]
    assert isinstance(sec, Section)
    para = sec.content[0]
    assert isinstance(para, Paragraph)
    assert "**bold**" in para.text
    assert "*italic*" in para.text
    assert "`code`" in para.text


def test_ingest_code_block():
    md = """## Code

```python
print("hello")
```
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    code_blocks = [b for b in sec.content if isinstance(b, CodeBlock)]
    assert len(code_blocks) == 1
    assert "print" in code_blocks[0].code
    assert code_blocks[0].language == "python"


def test_ingest_table():
    md = """## Data

| Name  | Value |
|-------|-------|
| A     | 1     |
| B     | 2     |
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    tables = [b for b in sec.content if isinstance(b, Table)]
    assert len(tables) == 1
    assert tables[0].headers == ["Name", "Value"]
    assert len(tables[0].rows) == 2
    assert tables[0].rows[0] == ["A", "1"]


def test_ingest_ordered_list():
    md = """## Results

1. First item
2. Second item
3. Third item
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    lists = [b for b in sec.content if isinstance(b, ItemList)]
    assert len(lists) == 1
    assert lists[0].ordered is True
    assert len(lists[0].items) == 3
    assert lists[0].items[0].text == "First item"


def test_ingest_unordered_list():
    md = """## Findings

- Point A
- Point B
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    lists = [b for b in sec.content if isinstance(b, ItemList)]
    assert len(lists) == 1
    assert lists[0].ordered is False


def test_ingest_image_as_figure():
    md = """## Results

![Experimental setup](figures/setup.png)
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    figs = [b for b in sec.content if isinstance(b, Figure)]
    assert len(figs) == 1
    assert figs[0].path == "figures/setup.png"
    assert figs[0].caption == "Experimental setup"


def test_ingest_link():
    md = """## Intro

See [the paper](http://example.com) for details.
"""
    doc = ingest_markdown(md)
    sec = doc.content[0]
    para = sec.content[0]
    assert isinstance(para, Paragraph)
    assert "[the paper](http://example.com)" in para.text


def test_ingest_sample_fixture():
    """Integration test: parse the sample.md fixture."""
    md = (FIXTURES / "sample.md").read_text()
    doc = ingest_markdown(md)

    assert doc.metadata.title == "Sample Research Paper"
    assert doc.metadata.author == "Jane Doe"
    assert doc.metadata.abstract.startswith("This paper demonstrates")

    # Check top-level sections
    sections = [b for b in doc.content if isinstance(b, Section)]
    titles = [s.title for s in sections]
    assert "Introduction" in titles
    assert "Methods" in titles
    assert "Results" in titles
    assert "Conclusion" in titles

    # Methods should have subsections
    methods = next(s for s in sections if s.title == "Methods")
    sub_titles = [b.title for b in methods.content if isinstance(b, Section)]
    assert "Data Collection" in sub_titles
    assert "Analysis" in sub_titles


def test_ingest_then_serialize():
    """End-to-end: ingest markdown, serialize to .tex, verify structure."""
    md = (FIXTURES / "sample.md").read_text()
    doc = ingest_markdown(md)
    tex = serialize(doc)

    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex
    assert "\\end{document}" in tex
    assert "\\section{Introduction}" in tex
    assert "\\section{Methods}" in tex
    assert "\\subsection{Data Collection}" in tex
    assert "\\begin{table}" in tex
    assert "\\begin{lstlisting}" in tex
    assert "\\begin{enumerate}" in tex
    assert "\\begin{itemize}" in tex
