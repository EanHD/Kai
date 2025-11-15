"""Unit tests for ResponsePostProcessor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from src.core.response_processor import ResponsePostProcessor


@pytest.fixture
def processor():
    """Create response processor."""
    return ResponsePostProcessor()


def test_remove_search_tags(processor):
    """Test removal of search tags."""
    text = """Here's my answer.

<search>Samsung 50E 21700 datasheet</search>
<search>Molicel P42A specifications</search>

Based on the data, the capacity is 5.0Ah."""

    result = processor.process(text)

    assert "<search>" not in result["text"]
    assert "</search>" not in result["text"]
    assert "Based on the data" in result["text"]


def test_extract_searches_to_metadata(processor):
    """Test that searches are extracted before removal."""
    text = """<search>Samsung 50E specs</search>
<search>battery capacity</search>
The answer is 5.0Ah."""

    result = processor.process(text)

    assert "searches_performed" in result["metadata"]
    assert len(result["metadata"]["searches_performed"]) == 2
    assert "Samsung 50E specs" in result["metadata"]["searches_performed"]
    assert "battery capacity" in result["metadata"]["searches_performed"]


def test_remove_thinking_tags(processor):
    """Test removal of thinking/reasoning tags."""
    text = """<thinking>
Let me calculate this carefully.
</thinking>

The answer is 42."""

    result = processor.process(text)

    assert "<thinking>" not in result["text"]
    assert "The answer is 42" in result["text"]


def test_extract_sources(processor):
    """Test extraction of source citations."""
    text = """According to Battery Mooch, the P42A has 4.2Ah capacity.
Based on official Samsung specs, the voltage is 3.6V."""

    result = processor.process(text)

    assert "sources_cited" in result["metadata"]
    sources = result["metadata"]["sources_cited"]
    assert any("Battery Mooch" in s for s in sources)
    assert any("Samsung" in s for s in sources)


def test_extract_urls(processor):
    """Test extraction of URLs as sources."""
    text = """Check https://www.example.com/specs for details.
Also see www.manufacturer.com/datasheet."""

    result = processor.process(text)

    sources = result["metadata"].get("sources_cited", [])
    assert any("example.com" in s for s in sources)


def test_normalize_whitespace(processor):
    """Test whitespace normalization."""
    text = """Line 1




Line 2    with    extra    spaces"""

    result = processor.process(text)

    # Should have max 2 newlines between content
    assert "\n\n\n" not in result["text"]
    # Should normalize spaces
    assert "   " not in result["text"]


def test_preserve_content(processor):
    """Test that important content is preserved."""
    text = """<search>test query</search>

The Samsung 50E has:
- Capacity: 5.0Ah
- Voltage: 3.6V
- Max discharge: 10A

According to manufacturer specs."""

    result = processor.process(text)

    # Content should be preserved
    assert "5.0Ah" in result["text"]
    assert "3.6V" in result["text"]
    assert "10A" in result["text"]
    # Tags should be removed
    assert "<search>" not in result["text"]


def test_empty_metadata_when_clean(processor):
    """Test that clean responses don't generate spurious metadata."""
    text = "This is a clean response with no tags or sources."

    result = processor.process(text)

    # Should have text
    assert result["text"] == text.strip()
    # Metadata should be empty or minimal
    metadata = result["metadata"]
    assert not metadata.get("searches_performed")
    assert not metadata.get("sources_cited")


def test_multiple_processing_safe(processor):
    """Test that processing same text twice is safe."""
    text = "<search>query</search>Answer"

    result1 = processor.process(text)
    result2 = processor.process(result1["text"])

    # Second processing should be safe
    assert result2["text"] == result1["text"]
    # Shouldn't find new searches in already-cleaned text
    assert not result2["metadata"].get("searches_performed")
