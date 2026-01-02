import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage:
- **search_course_content**: Use for questions about specific course content or detailed educational materials
- **get_course_outline**: Use for questions about course structure, syllabus, lesson list, or what topics a course covers
- **Sequential tool calls**: You may use tools sequentially if one tool's results inform the next
  - Example: get_course_outline to identify lessons, then search_course_content for specific content
  - Use judiciously - simple queries need only one tool call
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline questions** (e.g., "What lessons are in X?", "Show me the course structure", "What does the course cover?"): Use get_course_outline tool, then present course title, course link, and complete lesson list with lesson numbers and titles
- **Course content questions** (e.g., "Explain X from lesson Y", "What does the course say about Z?"): Use search_course_content tool
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the tool"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls with support for up to 2 sequential rounds.

        This method implements a loop that allows Claude to make sequential tool calls
        within a single user query. For example:
        - Round 1: get_course_outline to identify lessons
        - Round 2: search_course_content for specific lesson content

        Termination conditions:
        1. Claude returns stop_reason != "tool_use" (decides to finish)
        2. round_count reaches MAX_ROUNDS (2)
        3. Tool execution error (passed to Claude as tool_result)

        IMPORTANT: Tools must remain available in all API calls within the loop
        to enable Claude to make subsequent tool calls.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        MAX_ROUNDS = 2
        messages = base_params["messages"].copy()
        current_response = initial_response
        round_count = 0

        while round_count < MAX_ROUNDS:
            round_count += 1
            print(f"[AIGenerator] Tool execution round {round_count}/{MAX_ROUNDS}")

            # Add AI's tool use response
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tool calls and collect results
            tool_results = []
            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    print(f"[AIGenerator] Executing tool: {content_block.name}")
                    tool_result = tool_manager.execute_tool(
                        content_block.name,
                        **content_block.input
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

            # Add tool results as single message
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Prepare follow-up API call WITH tools still available (critical for multi-round)
            follow_up_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"]
            }

            # Keep tools available for subsequent rounds
            if "tools" in base_params:
                follow_up_params["tools"] = base_params["tools"]
                follow_up_params["tool_choice"] = {"type": "auto"}

            # Get follow-up response
            current_response = self.client.messages.create(**follow_up_params)
            print(f"[AIGenerator] Round {round_count} stop_reason: {current_response.stop_reason}")

            # Termination check: if Claude decides to finish, break loop
            if current_response.stop_reason != "tool_use":
                print(f"[AIGenerator] Terminating: Claude finished (stop_reason={current_response.stop_reason})")
                break

        # If we hit max rounds and Claude still wants to use tools, log it
        if round_count >= MAX_ROUNDS and current_response.stop_reason == "tool_use":
            print(f"[AIGenerator] Max rounds ({MAX_ROUNDS}) reached, returning current response")

        return current_response.content[0].text