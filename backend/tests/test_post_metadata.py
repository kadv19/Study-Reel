import os

import pytest

from app.engine.gemini_client import generate_topics_for_module
from app.engine.post_metadata import generate_post_metadata
from app.schemas import PostMetadata


MODULES = {
    "Data Structures": """
    Arrays, linked lists, stacks, queues, circular queues,
    and complexity analysis.
    """,
    "Computer Networks": """
    OSI model, TCP/IP, Ethernet, framing, error detection,
    flow control, and MAC protocols.
    """,
    "DBMS": """
    ER model, relational model, SQL, normalization,
    transactions, concurrency control, and recovery.
    """,
}


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured",
)
@pytest.mark.parametrize("module_name,module_text", MODULES.items())
def test_post_metadata_live(module_name, module_text):
    topics = generate_topics_for_module(module_text)

    metadata = generate_post_metadata(module_name, topics)

    assert isinstance(metadata, PostMetadata)

    assert metadata.caption
    assert len(metadata.caption) <= 2200

    assert 3 <= len(metadata.hashtags) <= 30

    assert all(isinstance(tag, str) for tag in metadata.hashtags)

    assert 0 <= metadata.cover_slide < len(topics)