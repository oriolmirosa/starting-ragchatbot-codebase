"""Pytest configuration and shared fixtures for RAG system tests"""
import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add backend directory to path so we can import modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from models import Course, Lesson, CourseChunk
from vector_store import VectorStore
from document_processor import DocumentProcessor
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from config import Config


@pytest.fixture
def test_config():
    """Create a test configuration with temporary database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        config.CHROMA_PATH = os.path.join(tmpdir, "test_chroma_db")
        config.CHUNK_SIZE = 200  # Smaller chunks for faster tests
        config.CHUNK_OVERLAP = 50
        config.MAX_RESULTS = 3  # Non-zero for functional tests
        config.ANTHROPIC_API_KEY = "test-key-placeholder"
        yield config


@pytest.fixture
def test_config_zero_results():
    """Config with MAX_RESULTS=0 to test the bug"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        config.CHROMA_PATH = os.path.join(tmpdir, "test_chroma_db")
        config.MAX_RESULTS = 0  # This is the bug we're testing
        yield config


@pytest.fixture
def test_course_file():
    """Path to test course data file"""
    return os.path.join(os.path.dirname(__file__), "test_data", "test_course.txt")


@pytest.fixture
def sample_course():
    """Create a sample Course object for testing"""
    return Course(
        title="Introduction to Testing",
        course_link="https://example.com/testing-course",
        instructor="Test Instructor",
        lessons=[
            Lesson(
                lesson_number=0,
                title="Getting Started",
                lesson_link="https://example.com/testing-course/lesson-0"
            ),
            Lesson(
                lesson_number=1,
                title="Unit Testing Basics",
                lesson_link="https://example.com/testing-course/lesson-1"
            ),
            Lesson(
                lesson_number=2,
                title="Integration Testing",
                lesson_link="https://example.com/testing-course/lesson-2"
            )
        ]
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Create sample course chunks for testing"""
    return [
        CourseChunk(
            content="Course Introduction to Testing Lesson 0 content: This is the introduction to testing. Testing is crucial for software quality.",
            course_title=sample_course.title,
            lesson_number=0,
            chunk_index=0
        ),
        CourseChunk(
            content="Course Introduction to Testing Lesson 1 content: Unit testing focuses on testing individual components in isolation. Each test should verify one specific behavior.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=1
        ),
        CourseChunk(
            content="Course Introduction to Testing Lesson 2 content: Integration tests verify that components work together correctly. They test the interactions between modules.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=2
        )
    ]


@pytest.fixture
def vector_store(test_config):
    """Create a vector store instance with test config"""
    store = VectorStore(
        chroma_path=test_config.CHROMA_PATH,
        embedding_model=test_config.EMBEDDING_MODEL,
        max_results=test_config.MAX_RESULTS
    )
    yield store
    # Cleanup
    if os.path.exists(test_config.CHROMA_PATH):
        shutil.rmtree(test_config.CHROMA_PATH)


@pytest.fixture
def vector_store_zero_results(test_config_zero_results):
    """Vector store with MAX_RESULTS=0 (bug scenario)"""
    store = VectorStore(
        chroma_path=test_config_zero_results.CHROMA_PATH,
        embedding_model=test_config_zero_results.EMBEDDING_MODEL,
        max_results=test_config_zero_results.MAX_RESULTS
    )
    yield store
    # Cleanup
    if os.path.exists(test_config_zero_results.CHROMA_PATH):
        shutil.rmtree(test_config_zero_results.CHROMA_PATH)


@pytest.fixture
def populated_vector_store(vector_store, sample_course, sample_chunks):
    """Vector store pre-populated with test data"""
    vector_store.add_course_metadata(sample_course)
    vector_store.add_course_content(sample_chunks)
    return vector_store


@pytest.fixture
def document_processor(test_config):
    """Create a document processor instance"""
    return DocumentProcessor(
        chunk_size=test_config.CHUNK_SIZE,
        chunk_overlap=test_config.CHUNK_OVERLAP
    )


@pytest.fixture
def course_search_tool(populated_vector_store):
    """Create CourseSearchTool with populated data"""
    return CourseSearchTool(populated_vector_store)


@pytest.fixture
def course_outline_tool(populated_vector_store):
    """Create CourseOutlineTool with populated data"""
    return CourseOutlineTool(populated_vector_store)


@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """Create ToolManager with registered tools"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager


@pytest.fixture
def mock_anthropic_response():
    """Mock response from Anthropic API (text only, no tool use)"""
    class MockContent:
        def __init__(self, text):
            self.text = text
            self.type = "text"

    class MockResponse:
        def __init__(self, text, stop_reason="end_turn"):
            self.content = [MockContent(text)]
            self.stop_reason = stop_reason

    return MockResponse


@pytest.fixture
def mock_anthropic_tool_use_response():
    """Mock response from Anthropic API with tool use"""
    class MockToolUseContent:
        def __init__(self, tool_name, tool_input, tool_id):
            self.type = "tool_use"
            self.name = tool_name
            self.input = tool_input
            self.id = tool_id

    class MockTextContent:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    class MockResponse:
        def __init__(self, tool_name, tool_input, tool_id="test-tool-id"):
            self.content = [
                MockTextContent("I'll search for that information."),
                MockToolUseContent(tool_name, tool_input, tool_id)
            ]
            self.stop_reason = "tool_use"

    return MockResponse
