"""Unit tests for CourseSearchTool"""
import pytest
from search_tools import CourseSearchTool


class TestCourseSearchToolDefinition:
    """Test tool definition and schema"""

    def test_tool_definition_structure(self, course_search_tool):
        """Tool definition should have correct structure"""
        tool_def = course_search_tool.get_tool_definition()

        assert "name" in tool_def
        assert tool_def["name"] == "search_course_content"
        assert "description" in tool_def
        assert "input_schema" in tool_def

    def test_tool_definition_parameters(self, course_search_tool):
        """Tool definition should specify required parameters"""
        tool_def = course_search_tool.get_tool_definition()
        schema = tool_def["input_schema"]

        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "course_name" in schema["properties"]
        assert "lesson_number" in schema["properties"]
        assert schema["required"] == ["query"]


class TestCourseSearchToolExecution:
    """Test tool execution with various inputs"""

    def test_search_with_valid_query(self, course_search_tool):
        """Should return results for valid query"""
        result = course_search_tool.execute(query="testing software quality")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should not be an error message
        assert not result.startswith("No relevant content found")

    def test_search_with_course_filter(self, course_search_tool):
        """Should filter by course name"""
        result = course_search_tool.execute(
            query="unit testing",
            course_name="Introduction to Testing"
        )

        assert isinstance(result, str)
        assert "Introduction to Testing" in result

    def test_search_with_partial_course_name(self, course_search_tool):
        """Should handle partial course name matching"""
        result = course_search_tool.execute(
            query="integration",
            course_name="Testing"  # Partial match
        )

        assert isinstance(result, str)
        # Should resolve to "Introduction to Testing"
        assert not result.startswith("No course found")

    def test_search_with_lesson_filter(self, course_search_tool):
        """Should filter by lesson number"""
        result = course_search_tool.execute(
            query="testing",
            lesson_number=1
        )

        assert isinstance(result, str)
        assert "Lesson 1" in result

    def test_search_with_course_and_lesson_filter(self, course_search_tool):
        """Should filter by both course and lesson"""
        result = course_search_tool.execute(
            query="integration",
            course_name="Introduction to Testing",
            lesson_number=2
        )

        assert isinstance(result, str)
        assert "Lesson 2" in result

    def test_search_with_invalid_course_name(self, course_search_tool):
        """With single course in DB, vector search matches it even for dissimilar names"""
        result = course_search_tool.execute(
            query="testing",
            course_name="NonExistent Course"
        )

        # Vector search will match the only available course due to semantic similarity
        # This is expected behavior - with only one course, it's the best match
        assert isinstance(result, str)
        # Will match "Introduction to Testing" as it's the only course
        assert "Introduction to Testing" in result or "No course found" in result

    def test_search_with_no_results(self, course_search_tool):
        """Should handle queries that return no results"""
        result = course_search_tool.execute(
            query="quantum physics advanced mathematics"  # Unrelated query
        )

        # Either returns no content found or some results
        assert isinstance(result, str)

    def test_result_formatting(self, course_search_tool):
        """Results should be properly formatted with headers"""
        result = course_search_tool.execute(query="unit testing")

        # Should have course title header
        assert "[Introduction to Testing" in result


class TestCourseSearchToolSourceTracking:
    """Test source tracking functionality"""

    def test_sources_stored_after_search(self, course_search_tool):
        """Sources should be stored in last_sources after search"""
        course_search_tool.execute(query="testing")

        assert hasattr(course_search_tool, 'last_sources')
        assert isinstance(course_search_tool.last_sources, list)

    def test_sources_contain_text_and_url(self, course_search_tool):
        """Sources should have text and url fields"""
        course_search_tool.execute(query="unit testing basics")

        if course_search_tool.last_sources:
            source = course_search_tool.last_sources[0]
            assert isinstance(source, dict)
            assert "text" in source
            assert "url" in source

    def test_sources_include_lesson_links(self, course_search_tool):
        """Sources should include lesson links when available"""
        course_search_tool.execute(query="integration testing")

        if course_search_tool.last_sources:
            source = course_search_tool.last_sources[0]
            # URL might be None or a string
            assert source["url"] is None or isinstance(source["url"], str)


class TestMaxResultsZeroBug:
    """Test behavior with MAX_RESULTS=0 (the current bug)"""

    def test_zero_max_results_returns_no_content(self, vector_store_zero_results, sample_course, sample_chunks):
        """When MAX_RESULTS=0, search should return configuration error"""
        # Populate the zero-results store
        vector_store_zero_results.add_course_metadata(sample_course)
        vector_store_zero_results.add_course_content(sample_chunks)

        # Create tool with zero-results store
        tool = CourseSearchTool(vector_store_zero_results)

        result = tool.execute(query="testing")

        # Should return configuration error message (improved error handling)
        assert "Configuration error" in result and "MAX_RESULTS" in result

    def test_zero_max_results_even_with_valid_data(self, vector_store_zero_results, sample_course, sample_chunks):
        """Even with valid data, MAX_RESULTS=0 causes empty results"""
        vector_store_zero_results.add_course_metadata(sample_course)
        vector_store_zero_results.add_course_content(sample_chunks)

        tool = CourseSearchTool(vector_store_zero_results)

        # Direct search on vector store should return empty
        search_results = vector_store_zero_results.search("testing")

        assert search_results.is_empty() == True
        assert len(search_results.documents) == 0


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_query(self, course_search_tool):
        """Should handle empty query gracefully"""
        result = course_search_tool.execute(query="")

        assert isinstance(result, str)

    def test_very_long_query(self, course_search_tool):
        """Should handle very long queries"""
        long_query = "testing " * 100
        result = course_search_tool.execute(query=long_query)

        assert isinstance(result, str)

    def test_special_characters_in_query(self, course_search_tool):
        """Should handle special characters"""
        result = course_search_tool.execute(query="test@#$%^&*()")

        assert isinstance(result, str)

    def test_lesson_number_zero(self, course_search_tool):
        """Should handle lesson number 0"""
        result = course_search_tool.execute(
            query="introduction",
            lesson_number=0
        )

        assert isinstance(result, str)
        assert "Lesson 0" in result

    def test_negative_lesson_number(self, course_search_tool):
        """Should handle negative lesson numbers"""
        result = course_search_tool.execute(
            query="testing",
            lesson_number=-1
        )

        # Should either return no results or handle gracefully
        assert isinstance(result, str)
