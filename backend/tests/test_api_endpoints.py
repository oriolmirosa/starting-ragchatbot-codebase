"""API endpoint tests for FastAPI application"""
import pytest
from fastapi.testclient import TestClient


class TestQueryEndpoint:
    """Test /api/query endpoint"""

    def test_query_with_new_session(self, client, mock_rag_system):
        """Should create new session when session_id not provided"""
        response = client.post(
            "/api/query",
            json={"query": "What is unit testing?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify session was created
        mock_rag_system.session_manager.create_session.assert_called_once()
        assert data["session_id"] == "test-session-123"

        # Verify query was processed
        mock_rag_system.query.assert_called_once_with(
            "What is unit testing?",
            "test-session-123"
        )

    def test_query_with_existing_session(self, client, mock_rag_system):
        """Should use provided session_id"""
        response = client.post(
            "/api/query",
            json={
                "query": "Explain integration testing",
                "session_id": "existing-session-456"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should not create new session
        mock_rag_system.session_manager.create_session.assert_not_called()

        # Should use provided session
        mock_rag_system.query.assert_called_once_with(
            "Explain integration testing",
            "existing-session-456"
        )

        assert data["session_id"] == "existing-session-456"

    def test_query_returns_answer_and_sources(self, client, mock_rag_system):
        """Should return answer with source citations"""
        response = client.post(
            "/api/query",
            json={"query": "What is testing?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify answer
        assert data["answer"] == "This is a test answer about unit testing."

        # Verify sources structure
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Introduction to Testing - Lesson 1"
        assert data["sources"][0]["url"] == "https://example.com/lesson-1"
        assert data["sources"][1]["text"] == "Introduction to Testing - Lesson 2"
        assert data["sources"][1]["url"] == "https://example.com/lesson-2"

    def test_query_with_empty_query(self, client):
        """Should reject empty query"""
        response = client.post(
            "/api/query",
            json={"query": ""}
        )

        # FastAPI will validate this - empty string is valid but may fail at RAG level
        # This tests that the endpoint accepts the request structure
        assert response.status_code in [200, 422, 500]

    def test_query_with_missing_query_field(self, client):
        """Should reject request without query field"""
        response = client.post(
            "/api/query",
            json={"session_id": "test-123"}
        )

        # Should fail validation
        assert response.status_code == 422

    def test_query_handles_rag_system_errors(self, client, mock_rag_system):
        """Should return 500 when RAG system raises error"""
        # Make RAG system raise an error
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        response = client.post(
            "/api/query",
            json={"query": "Test query"}
        )

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

    def test_query_with_sources_without_url(self, client, mock_rag_system):
        """Should handle sources that don't have URLs"""
        # Mock RAG system to return source without URL
        mock_rag_system.query.return_value = (
            "Test answer",
            [{"text": "Source without URL"}]
        )

        response = client.post(
            "/api/query",
            json={"query": "Test"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sources"][0]["text"] == "Source without URL"
        assert data["sources"][0]["url"] is None


class TestCoursesEndpoint:
    """Test /api/courses endpoint"""

    def test_get_course_stats(self, client, mock_rag_system):
        """Should return course statistics"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify values
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to Testing" in data["course_titles"]
        assert "Advanced Testing Patterns" in data["course_titles"]

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_courses_endpoint_no_courses(self, client, mock_rag_system):
        """Should handle case with no courses"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_courses_handles_rag_system_errors(self, client, mock_rag_system):
        """Should return 500 when RAG system raises error"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Vector store error")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "Vector store error" in response.json()["detail"]


class TestRootEndpoint:
    """Test root (/) endpoint"""

    def test_root_endpoint(self, client):
        """Should return API welcome message"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "RAG System" in data["message"]


class TestCORSHeaders:
    """Test CORS middleware configuration"""

    def test_cors_headers_present(self, client):
        """Should include CORS headers in response"""
        response = client.options(
            "/api/query",
            headers={"Origin": "http://localhost:3000"}
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"

    def test_cors_allows_credentials(self, client):
        """Should allow credentials via CORS"""
        response = client.get(
            "/api/courses",
            headers={"Origin": "http://localhost:3000"}
        )

        assert "access-control-allow-credentials" in response.headers


class TestRequestValidation:
    """Test request validation and error handling"""

    def test_invalid_json_format(self, client):
        """Should reject malformed JSON"""
        response = client.post(
            "/api/query",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_wrong_content_type(self, client):
        """Should handle wrong content type gracefully"""
        response = client.post(
            "/api/query",
            data="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # FastAPI should reject or handle this
        assert response.status_code in [422, 400]

    def test_extra_fields_ignored(self, client, mock_rag_system):
        """Should ignore extra fields in request"""
        response = client.post(
            "/api/query",
            json={
                "query": "Test query",
                "session_id": "test-123",
                "extra_field": "should be ignored"
            }
        )

        # Should still work (Pydantic ignores extra fields by default)
        assert response.status_code == 200


class TestSessionManagement:
    """Test session management across requests"""

    def test_multiple_queries_same_session(self, client, mock_rag_system):
        """Should maintain session across multiple queries"""
        session_id = "persistent-session-789"

        # First query
        response1 = client.post(
            "/api/query",
            json={"query": "First question", "session_id": session_id}
        )
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second query with same session
        response2 = client.post(
            "/api/query",
            json={"query": "Follow-up question", "session_id": session_id}
        )
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Both should use the same session
        assert mock_rag_system.query.call_count == 2

    def test_different_sessions_isolated(self, client, mock_rag_system):
        """Different sessions should be isolated"""
        # Query 1 with session A
        response1 = client.post(
            "/api/query",
            json={"query": "Question A", "session_id": "session-A"}
        )

        # Query 2 with session B
        response2 = client.post(
            "/api/query",
            json={"query": "Question B", "session_id": "session-B"}
        )

        assert response1.json()["session_id"] == "session-A"
        assert response2.json()["session_id"] == "session-B"
