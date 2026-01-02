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


# ============ API Testing Fixtures ============

@pytest.fixture
def mock_rag_system(mocker):
    """Mock RAGSystem for API testing"""
    from rag_system import RAGSystem

    mock_system = mocker.Mock(spec=RAGSystem)

    # Mock query method to return test data
    mock_system.query.return_value = (
        "This is a test answer about unit testing.",
        [
            {"text": "Introduction to Testing - Lesson 1", "url": "https://example.com/lesson-1"},
            {"text": "Introduction to Testing - Lesson 2", "url": "https://example.com/lesson-2"}
        ]
    )

    # Mock course analytics
    mock_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Introduction to Testing", "Advanced Testing Patterns"]
    }

    # Mock session manager
    mock_session_manager = mocker.Mock()
    mock_session_manager.create_session.return_value = "test-session-123"
    mock_system.session_manager = mock_session_manager

    return mock_system


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app with mocked RAG system"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional

    # Create test app (avoiding static file mounting)
    app = FastAPI(title="Test RAG System")

    # Enable CORS for testing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pydantic models (copied from app.py)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class Source(BaseModel):
        text: str
        url: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Source]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # API Endpoints (using mock_rag_system)
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)
            source_objects = [Source(text=s["text"], url=s.get("url")) for s in sources]

            return QueryResponse(
                answer=answer,
                sources=source_objects,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "Course Materials RAG System API"}

    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    from fastapi.testclient import TestClient
    return TestClient(test_app)
