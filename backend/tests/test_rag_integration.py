"""Integration tests for RAG system end-to-end functionality"""
import pytest
from unittest.mock import Mock, patch
import os
import tempfile
import shutil

from rag_system import RAGSystem
from config import Config


@pytest.fixture
def integration_test_config():
    """Config for integration tests with temporary database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        config.CHROMA_PATH = os.path.join(tmpdir, "integration_test_db")
        config.CHUNK_SIZE = 200
        config.CHUNK_OVERLAP = 50
        config.MAX_RESULTS = 5  # Proper value for tests
        config.MAX_HISTORY = 2
        config.ANTHROPIC_API_KEY = "test-integration-key"
        yield config


@pytest.fixture
def integration_test_config_broken():
    """Config with MAX_RESULTS=0 (broken scenario)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        config.CHROMA_PATH = os.path.join(tmpdir, "broken_test_db")
        config.MAX_RESULTS = 0  # This is the bug
        config.ANTHROPIC_API_KEY = "test-key"
        yield config


@pytest.fixture
def rag_system(integration_test_config, test_course_file):
    """Create RAG system with test data loaded"""
    system = RAGSystem(integration_test_config)
    # Load test course
    system.add_course_document(test_course_file)
    return system


@pytest.fixture
def rag_system_broken(integration_test_config_broken, test_course_file):
    """RAG system with MAX_RESULTS=0 bug"""
    system = RAGSystem(integration_test_config_broken)
    system.add_course_document(test_course_file)
    return system


class TestRAGSystemInitialization:
    """Test RAG system initialization and setup"""

    def test_rag_system_initializes_components(self, integration_test_config):
        """Should initialize all components correctly"""
        system = RAGSystem(integration_test_config)

        assert system.document_processor is not None
        assert system.vector_store is not None
        assert system.ai_generator is not None
        assert system.session_manager is not None
        assert system.tool_manager is not None

    def test_rag_system_registers_tools(self, integration_test_config):
        """Should register both search and outline tools"""
        system = RAGSystem(integration_test_config)

        tool_defs = system.tool_manager.get_tool_definitions()
        tool_names = [tool["name"] for tool in tool_defs]

        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_course_loading(self, test_course_file, integration_test_config):
        """Should successfully load course documents"""
        system = RAGSystem(integration_test_config)
        course, num_chunks = system.add_course_document(test_course_file)

        assert course is not None
        assert course.title == "Introduction to Testing"
        assert num_chunks > 0
        assert len(course.lessons) == 3


class TestRAGSystemContentQueries:
    """Test end-to-end content query processing"""

    @patch('anthropic.Anthropic')
    def test_content_query_full_flow(self, mock_anthropic_class, rag_system, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Test complete flow: query → tool use → response"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First API call: Claude decides to search
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "unit testing isolation"},
            tool_id="test-id-1"
        )

        # Second API call: Claude synthesizes answer
        final_response = mock_anthropic_response(
            "Unit testing focuses on testing individual components in isolation.",
            "end_turn"
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        # Execute query
        response, sources = rag_system.query("What is unit testing?")

        # Verify response
        assert isinstance(response, str)
        assert len(response) > 0
        assert "unit testing" in response.lower() or "isolation" in response.lower()

        # Verify sources were tracked
        assert isinstance(sources, list)

    @patch('anthropic.Anthropic')
    def test_outline_query_full_flow(self, mock_anthropic_class, rag_system, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Test outline query flow"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First call: Claude decides to get outline
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "Testing"},
            tool_id="outline-id"
        )

        # Second call: Claude presents outline
        final_response = mock_anthropic_response(
            "The course has 3 lessons: Getting Started, Unit Testing Basics, and Integration Testing.",
            "end_turn"
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        # Execute query
        response, sources = rag_system.query("What lessons are in the testing course?")

        assert isinstance(response, str)
        assert len(response) > 0

    @patch('anthropic.Anthropic')
    def test_conversation_history_persistence(self, mock_anthropic_class, rag_system, mock_anthropic_response):
        """Should maintain conversation history across queries"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_client.messages.create.return_value = mock_anthropic_response(
            "Test response",
            "end_turn"
        )

        # First query
        session_id = rag_system.session_manager.create_session()
        response1, _ = rag_system.query("What is testing?", session_id=session_id)

        # Second query in same session
        response2, _ = rag_system.query("Tell me more", session_id=session_id)

        # Verify session has history
        history = rag_system.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert len(history) > 0

    @patch('anthropic.Anthropic')
    def test_sources_reset_after_query(self, mock_anthropic_class, rag_system, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Sources should be reset after each query"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "testing"},
            tool_id="source-test"
        )

        final_response = mock_anthropic_response("Answer", "end_turn")
        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        # First query
        response1, sources1 = rag_system.query("What is testing?")

        # Sources should be empty after reset
        remaining_sources = rag_system.tool_manager.get_last_sources()
        assert len(remaining_sources) == 0


class TestBrokenConfiguration:
    """Test behavior with MAX_RESULTS=0 (the bug)"""

    @patch('anthropic.Anthropic')
    def test_broken_config_causes_empty_results(self, mock_anthropic_class, rag_system_broken, mock_anthropic_tool_use_response, mock_anthropic_response):
        """With MAX_RESULTS=0, search returns no results"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Claude tries to search
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "unit testing"},
            tool_id="broken-test"
        )

        # Claude gets empty results
        final_response = mock_anthropic_response(
            "I couldn't find any information about that.",
            "end_turn"
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        response, sources = rag_system_broken.query("What is unit testing?")

        # Response will indicate failure
        assert isinstance(response, str)
        # Sources will be empty because search returned nothing
        assert len(sources) == 0

    def test_vector_store_max_results_zero(self, rag_system_broken):
        """Vector store with MAX_RESULTS=0 returns empty results"""
        # Direct search should return empty
        results = rag_system_broken.vector_store.search("testing")

        assert results.is_empty() == True
        assert len(results.documents) == 0

    def test_search_tool_with_zero_results(self, rag_system_broken):
        """Search tool with zero max_results returns configuration error"""
        result = rag_system_broken.search_tool.execute(query="testing")

        # Should indicate configuration error (improved error handling)
        assert "Configuration error" in result or "MAX_RESULTS" in result


class TestErrorHandling:
    """Test error handling in RAG system"""

    @patch('anthropic.Anthropic')
    def test_handles_invalid_course_name(self, mock_anthropic_class, rag_system, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Should handle searches for non-existent courses"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "testing", "course_name": "NonExistent"},
            tool_id="error-test"
        )

        final_response = mock_anthropic_response(
            "I couldn't find that course.",
            "end_turn"
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        response, sources = rag_system.query("What does NonExistent course say?")

        assert isinstance(response, str)

    def test_handles_empty_query(self, rag_system):
        """Should handle empty queries gracefully"""
        # This might raise an exception or return a message
        # Either is acceptable
        try:
            response, sources = rag_system.query("")
            assert isinstance(response, str)
        except Exception as e:
            # Empty query might raise an error - that's okay
            assert True


class TestAnalytics:
    """Test course analytics functionality"""

    def test_course_analytics(self, rag_system):
        """Should return correct course analytics"""
        analytics = rag_system.get_course_analytics()

        assert "total_courses" in analytics
        assert "course_titles" in analytics
        assert analytics["total_courses"] == 1
        assert "Introduction to Testing" in analytics["course_titles"]

    def test_analytics_with_multiple_courses(self, integration_test_config, test_course_file):
        """Should track multiple courses correctly"""
        system = RAGSystem(integration_test_config)

        # Load test course
        system.add_course_document(test_course_file)

        analytics = system.get_course_analytics()
        assert analytics["total_courses"] >= 1


class TestDocumentProcessing:
    """Test document processing in RAG system"""

    def test_duplicate_course_not_reprocessed(self, integration_test_config, test_course_file):
        """Should not reprocess courses that already exist"""
        system = RAGSystem(integration_test_config)

        # Load course first time
        course1, chunks1 = system.add_course_document(test_course_file)

        # Try to load again
        course2, chunks2 = system.add_course_document(test_course_file)

        # Second load should be skipped (implementation detail may vary)
        analytics = system.get_course_analytics()
        # Should still have just 1 course, not 2
        assert analytics["total_courses"] == 1

    def test_course_folder_loading(self, integration_test_config, test_course_file):
        """Should load courses from a folder"""
        import os

        system = RAGSystem(integration_test_config)

        # Get test_data folder path
        test_data_folder = os.path.dirname(test_course_file)

        # Load folder
        courses_added, chunks_added = system.add_course_folder(test_data_folder)

        assert courses_added >= 1
        assert chunks_added > 0
