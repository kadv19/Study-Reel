import os

import pytest

from app.engine.gemini_client import generate_topics_for_module
from app.schemas import MicroTopic, ALLOWED_LANGUAGES


MODULES = {
    "data_structures": """
Module 1: Data Structures

Introduction to data structures and abstract data types.
Arrays, linked lists, stacks and queues. Operations on stacks
and queues. Applications of stacks and queues. Circular queues.
Complexity analysis of basic operations.
""",

    "computer_networks": """
Module 2: Computer Networks

Introduction to computer networks and network architecture.
OSI reference model and TCP/IP protocol suite. Physical layer
and data link layer concepts. Ethernet, framing, error detection,
flow control and MAC protocols.
""",

    "dbms": """
Module 3: Database Management Systems

Database system concepts and architecture. Entity relationship
model, relational model, relational algebra and SQL. Functional
dependencies, normalization, normal forms and transaction
management. Concurrency control and database recovery.
""",

    "operating_systems": """
Module 4: Operating Systems

Operating system structures and services. Processes and threads.
CPU scheduling algorithms. Process synchronization and deadlocks.
Memory management, virtual memory, paging and segmentation.
File system implementation and disk scheduling.
""",

    "machine_learning": """
Module 5: Machine Learning

Introduction to machine learning and its applications. Supervised
and unsupervised learning. Linear regression, classification,
decision trees, k-nearest neighbours and clustering. Model
evaluation, training and testing.
""",
}


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not configured",
)
@pytest.mark.parametrize("module_name,module_text", MODULES.items())
def test_gemini_live(module_name, module_text):
    topics = generate_topics_for_module(module_text)

    assert isinstance(topics, list)
    assert len(topics) > 0

    for topic in topics:
        assert isinstance(topic, MicroTopic)

        # MicroTopic contract
        assert len(topic.header) <= 30
        assert len(topic.body) <= 140

        if topic.code_block is not None:
            lines = topic.code_block.splitlines()

            assert len(lines) <= 22

            for line in lines:
                assert len(line) <= 62

            assert topic.language_tag in ALLOWED_LANGUAGES