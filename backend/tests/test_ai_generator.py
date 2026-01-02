"""Unit tests for AIGenerator and tool calling behavior"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from ai_generator import AIGenerator


class TestAIGeneratorInitialization:
    """Test AIGenerator initialization"""

    def test_initialization_with_api_key(self):
        """Should initialize with API key and model"""
        generator = AIGenerator(api_key="test-key", model="claude-3-5-sonnet-20241022")

        assert generator.model == "claude-3-5-sonnet-20241022"
        assert generator.base_params["model"] == "claude-3-5-sonnet-20241022"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_system_prompt_contains_tool_instructions(self):
        """System prompt should include tool usage instructions"""
        assert "search_course_content" in AIGenerator.SYSTEM_PROMPT
        assert "get_course_outline" in AIGenerator.SYSTEM_PROMPT
        assert "tool" in AIGenerator.SYSTEM_PROMPT.lower()


class TestAIGeneratorBasicResponse:
    """Test basic response generation without tools"""

    @patch('anthropic.Anthropic')
    def test_generate_response_without_tools(self, mock_anthropic_class, mock_anthropic_response):
        """Should generate response without using tools"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = mock_anthropic_response(
            "Python is a high-level programming language.",
            stop_reason="end_turn"
        )

        generator = AIGenerator(api_key="test-key", model="test-model")
        response = generator.generate_response(
            query="What is Python?",
            tools=None,
            tool_manager=None
        )

        assert isinstance(response, str)
        assert len(response) > 0
        assert "Python" in response

    @patch('anthropic.Anthropic')
    def test_response_with_conversation_history(self, mock_anthropic_class, mock_anthropic_response):
        """Should include conversation history in system prompt"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = mock_anthropic_response(
            "Yes, it's very popular.",
            stop_reason="end_turn"
        )

        generator = AIGenerator(api_key="test-key", model="test-model")
        history = "User: What is Python?\nAssistant: A programming language."

        response = generator.generate_response(
            query="Is it popular?",
            conversation_history=history,
            tools=None,
            tool_manager=None
        )

        # Check that create was called with history in system prompt
        call_args = mock_client.messages.create.call_args
        assert history in call_args.kwargs["system"]


class TestAIGeneratorToolCalling:
    """Test tool calling behavior"""

    @patch('anthropic.Anthropic')
    def test_tools_included_in_request_when_provided(self, mock_anthropic_class, mock_anthropic_response):
        """Should include tools in API request when provided"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = mock_anthropic_response(
            "Here's what I found.",
            stop_reason="end_turn"
        )

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content", "description": "Search courses"}]

        generator.generate_response(
            query="What is testing?",
            tools=tools,
            tool_manager=None
        )

        # Verify tools were passed to API
        call_args = mock_client.messages.create.call_args
        assert "tools" in call_args.kwargs
        assert call_args.kwargs["tools"] == tools
        assert call_args.kwargs["tool_choice"] == {"type": "auto"}

    @patch('anthropic.Anthropic')
    def test_tool_execution_flow(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Should execute tool when Claude requests it"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First call: Claude requests tool use
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "unit testing"},
            tool_id="tool-123"
        )

        # Second call: Claude synthesizes final response
        final_response = mock_anthropic_response(
            "Unit testing is about testing individual components.",
            stop_reason="end_turn"
        )

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Unit tests focus on isolated components."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        response = generator.generate_response(
            query="What is unit testing?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="unit testing"
        )

        # Verify we got final response
        assert isinstance(response, str)
        assert len(response) > 0

        # Verify API was called twice (initial + follow-up)
        assert mock_client.messages.create.call_count == 2

    @patch('anthropic.Anthropic')
    def test_tool_result_included_in_followup(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Tool results should be included in follow-up request"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "testing"},
            tool_id="tool-456"
        )

        final_response = mock_anthropic_response("Based on the search results...", "end_turn")

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Test results from search"

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        generator.generate_response(
            query="Tell me about testing",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Check second API call includes tool results
        second_call_args = mock_client.messages.create.call_args_list[1]
        messages = second_call_args.kwargs["messages"]

        # Should have 3 messages: user query, assistant tool use, user tool result
        assert len(messages) == 3
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["content"] == "Test results from search"


class TestToolCallingDecision:
    """Test that AI correctly decides when to use tools"""

    @patch('anthropic.Anthropic')
    def test_content_query_triggers_search_tool(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Course content questions should trigger search tool"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Simulate Claude deciding to use search tool
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "machine learning basics", "course_name": "ML Course"},
            tool_id="tool-789"
        )

        final_response = mock_anthropic_response("Machine learning is...", "end_turn")
        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "ML content..."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [
            {"name": "search_course_content", "description": "Search course content"},
            {"name": "get_course_outline", "description": "Get course outline"}
        ]

        generator.generate_response(
            query="What does the ML course say about supervised learning?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify search_course_content was called (not outline)
        mock_tool_manager.execute_tool.assert_called_once()
        call_args = mock_tool_manager.execute_tool.call_args
        assert call_args[0][0] == "search_course_content"

    @patch('anthropic.Anthropic')
    def test_outline_query_triggers_outline_tool(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Course outline questions should trigger outline tool"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Simulate Claude deciding to use outline tool
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "Testing Course"},
            tool_id="tool-outline"
        )

        final_response = mock_anthropic_response("The course has 3 lessons...", "end_turn")
        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Course outline..."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [
            {"name": "search_course_content"},
            {"name": "get_course_outline"}
        ]

        generator.generate_response(
            query="What lessons are in the Testing Course?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify get_course_outline was called
        call_args = mock_tool_manager.execute_tool.call_args
        assert call_args[0][0] == "get_course_outline"


class TestErrorHandling:
    """Test error handling in tool execution"""

    @patch('anthropic.Anthropic')
    def test_handles_tool_execution_errors(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Should handle errors from tool execution gracefully"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test"},
            tool_id="tool-error"
        )

        final_response = mock_anthropic_response("I encountered an error...", "end_turn")
        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Error: Search failed"

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        # Should not raise exception, should return response
        response = generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert isinstance(response, str)


class TestSequentialToolCalling:
    """Test sequential (multi-round) tool calling behavior"""

    @patch('anthropic.Anthropic')
    def test_single_tool_call_still_works(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Backward compatibility: single-round tool calling unchanged"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock: tool_use → end_turn (single round, as before)
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "testing"},
            tool_id="test-1"
        )
        final_response = mock_anthropic_response("Here's what I found about testing.", "end_turn")

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Testing is important..."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        response = generator.generate_response(
            query="What is testing?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify: Tool executed once, 2 API calls (initial + follow-up), response returned
        assert mock_tool_manager.execute_tool.call_count == 1
        assert mock_client.messages.create.call_count == 2
        assert isinstance(response, str)
        assert "testing" in response.lower()

    @patch('anthropic.Anthropic')
    def test_two_rounds_executes_both_tools(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Verify two sequential tool calls work correctly"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock responses: tool_use → tool_use → end_turn (2 rounds)
        round1_response = mock_anthropic_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "Testing"},
            tool_id="round1"
        )
        round2_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "unit testing", "lesson_number": 2},
            tool_id="round2"
        )
        final_response = mock_anthropic_response("The course has 3 lessons. Lesson 2 covers unit testing...", "end_turn")

        mock_client.messages.create.side_effect = [round1_response, round2_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Course: Testing\nLesson 1: Intro\nLesson 2: Unit Testing\nLesson 3: Integration",
            "Unit testing focuses on isolated components..."
        ]

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [
            {"name": "get_course_outline"},
            {"name": "search_course_content"}
        ]

        response = generator.generate_response(
            query="What does lesson 2 of the Testing course cover?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify: Both tools executed in order, 3 API calls total
        assert mock_tool_manager.execute_tool.call_count == 2
        assert mock_client.messages.create.call_count == 3

        # Verify tools called in expected order
        first_call = mock_tool_manager.execute_tool.call_args_list[0]
        second_call = mock_tool_manager.execute_tool.call_args_list[1]
        assert first_call[0][0] == "get_course_outline"
        assert second_call[0][0] == "search_course_content"

        assert isinstance(response, str)

    @patch('anthropic.Anthropic')
    def test_stops_after_one_round_if_claude_finishes(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """Verify loop exits when Claude returns end_turn after round 1"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock: tool_use → end_turn (early termination)
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "testing"},
            tool_id="test-early"
        )
        final_response = mock_anthropic_response("Testing is important.", "end_turn")

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Testing info..."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        response = generator.generate_response(
            query="What is testing?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify: Only 1 tool execution, 2 API calls (not 3)
        assert mock_tool_manager.execute_tool.call_count == 1
        assert mock_client.messages.create.call_count == 2
        assert isinstance(response, str)

    @patch('anthropic.Anthropic')
    def test_max_two_rounds_enforced(self, mock_anthropic_class, mock_anthropic_tool_use_response):
        """Verify system caps at 2 rounds even if Claude wants more"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock: Always returns tool_use (would loop forever without cap)
        tool_use_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test"},
            tool_id="infinite"
        )

        # All responses are tool_use (infinite loop scenario)
        mock_client.messages.create.return_value = tool_use_response

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results..."

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [{"name": "search_course_content"}]

        response = generator.generate_response(
            query="Test",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify: Exactly 2 tool executions (rounds 1 and 2)
        assert mock_tool_manager.execute_tool.call_count == 2

        # Verify: 3 API calls total (initial + round1 + round2)
        assert mock_client.messages.create.call_count == 3

        # Should still return valid response (from round 2's tool_use text, if any)
        assert isinstance(response, str)

    @patch('anthropic.Anthropic')
    def test_tools_parameter_included_in_second_round(self, mock_anthropic_class, mock_anthropic_tool_use_response, mock_anthropic_response):
        """CRITICAL: Verify tools not removed from round 2 API call"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock: tool_use → tool_use → end_turn
        round1_response = mock_anthropic_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "Test"},
            tool_id="r1"
        )
        round2_response = mock_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test"},
            tool_id="r2"
        )
        final_response = mock_anthropic_response("Final answer", "end_turn")

        mock_client.messages.create.side_effect = [round1_response, round2_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        generator = AIGenerator(api_key="test-key", model="test-model")
        tools = [
            {"name": "get_course_outline"},
            {"name": "search_course_content"}
        ]

        generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify: Second API call (after round 1) includes tools parameter
        # This is the critical bug fix - old code removed tools
        second_call_args = mock_client.messages.create.call_args_list[1]
        assert "tools" in second_call_args.kwargs
        assert second_call_args.kwargs["tools"] == tools
        assert second_call_args.kwargs["tool_choice"] == {"type": "auto"}
