# RAG System Test Suite

## Overview
Comprehensive test suite for the RAG (Retrieval-Augmented Generation) chatbot system. Tests cover unit, integration, and edge cases to ensure system reliability.

## Quick Start

```bash
# Install dependencies
uv sync

# Run all tests
cd backend
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_search_tool.py -v

# Run tests matching pattern
uv run pytest tests/ -k "search" -v
```

## Test Structure

```
tests/
├── __init__.py                    # Package marker
├── conftest.py                    # Shared fixtures and configuration
├── test_search_tool.py           # CourseSearchTool unit tests (30 tests)
├── test_ai_generator.py          # AIGenerator unit tests (15 tests)
├── test_rag_integration.py       # RAG system integration tests (6 tests)
├── test_api_endpoints.py         # FastAPI endpoint tests (18 tests)
├── test_data/
│   └── test_course.txt           # Sample course for testing
├── TEST_RESULTS.md               # Detailed test results and analysis
├── FIXES_SUMMARY.md              # Summary of bugs found and fixed
└── README.md                     # This file
```

## Test Files

### test_search_tool.py
Tests for `CourseSearchTool` - the tool that searches course content.

**Test Classes:**
- `TestCourseSearchToolDefinition` - Tool schema validation
- `TestCourseSearchToolExecution` - Query execution with filters
- `TestCourseSearchToolSourceTracking` - Source citation tracking
- `TestMaxResultsZeroBug` - Zero results configuration bug
- `TestEdgeCases` - Edge cases and error conditions

**Key Tests:**
- ✅ Valid queries return results
- ✅ Course name filtering (exact and partial matches)
- ✅ Lesson number filtering
- ✅ Source tracking with URLs
- ✅ MAX_RESULTS=0 error handling
- ✅ Empty/long/special character queries

### test_ai_generator.py
Tests for `AIGenerator` - the component that calls Claude API.

**Test Classes:**
- `TestAIGeneratorInitialization` - Setup and configuration
- `TestAIGeneratorBasicResponse` - Non-tool responses
- `TestAIGeneratorToolCalling` - Tool execution flow
- `TestToolCallingDecision` - When to use which tool
- `TestErrorHandling` - Error scenarios

**Key Tests:**
- ✅ System prompt includes tool instructions
- ✅ Tools included in API request
- ✅ Two-stage API call pattern (initial → tool → synthesis)
- ✅ Tool results passed to follow-up request
- ✅ Conversation history integration
- ✅ Claude chooses correct tool for query type

### test_rag_integration.py
Integration tests for the complete RAG system flow.

**Test Classes:**
- `TestRAGSystemInitialization` - System setup
- `TestRAGSystemContentQueries` - End-to-end query processing
- `TestBrokenConfiguration` - MAX_RESULTS=0 impact
- `TestErrorHandling` - Error propagation
- `TestAnalytics` - Course statistics
- `TestDocumentProcessing` - Document loading

**Key Tests:**
- ✅ All components initialize correctly
- ✅ Tools registered properly
- ✅ Course documents load successfully
- ✅ Analytics return correct data
- ✅ Duplicate courses not reprocessed
- ⚠️ End-to-end queries (requires API key mocking)

### test_api_endpoints.py
Tests for FastAPI HTTP endpoints - API layer validation.

**Test Classes:**
- `TestQueryEndpoint` - POST /api/query tests
- `TestCoursesEndpoint` - GET /api/courses tests
- `TestRootEndpoint` - GET / tests
- `TestCORSHeaders` - CORS middleware validation
- `TestRequestValidation` - Request validation tests
- `TestSessionManagement` - Session handling tests

**Key Tests:**
- ✅ Query endpoint with/without session_id
- ✅ Returns proper answer and sources structure
- ✅ Validates required fields (422 errors)
- ✅ Error handling (500 on failures)
- ✅ Course statistics endpoint
- ✅ CORS headers present and configured correctly
- ✅ Request validation (malformed JSON, wrong content type)
- ✅ Session persistence across requests

## Fixtures (conftest.py)

### Configuration Fixtures
- `test_config` - Config with temporary DB and proper settings
- `test_config_zero_results` - Config with MAX_RESULTS=0 (bug scenario)

### Data Fixtures
- `test_course_file` - Path to sample course file
- `sample_course` - Course object with 3 lessons
- `sample_chunks` - Pre-chunked course content

### Component Fixtures
- `vector_store` - VectorStore with test config
- `populated_vector_store` - VectorStore with sample data loaded
- `document_processor` - DocumentProcessor instance
- `course_search_tool` - CourseSearchTool with data
- `course_outline_tool` - CourseOutlineTool with data
- `tool_manager` - ToolManager with registered tools

### Mock Fixtures
- `mock_anthropic_response` - Mock text-only API response
- `mock_anthropic_tool_use_response` - Mock tool-use API response

### API Testing Fixtures
- `mock_rag_system` - Mocked RAGSystem for API endpoint tests
- `test_app` - FastAPI test application (avoids static file mounting)
- `client` - TestClient for making HTTP requests

## Test Results

### Current Status
- **Total Tests**: 69
- **Passing**: 63 (91%)
- **Failing**: 6 (9% - all integration tests requiring valid API key)

### Component Coverage
| Component | Tests | Status |
|-----------|-------|--------|
| API Endpoints | 18 | ✅ All passing |
| CourseSearchTool | 30 | ✅ All passing |
| AIGenerator | 15 | ✅ All passing |
| RAG Integration | 0/6 | ⚠️ Requires API key |

### Known Issues
1. **Integration tests require valid API key** - 6 tests fail with auth errors
   - Expected behavior - these are true integration tests
   - Set `ANTHROPIC_API_KEY` in `.env` to run them
   - All other tests (63/69) use mocks and don't require API key

2. **Course name matching is fuzzy** - Vector search matches dissimilar names
   - Expected behavior with small test dataset
   - Would improve with more courses or similarity threshold

## Running Specific Tests

```bash
# Test only API endpoints
uv run pytest tests/test_api_endpoints.py -v

# Test only CourseSearchTool
uv run pytest tests/test_search_tool.py -v

# Test only AIGenerator
uv run pytest tests/test_ai_generator.py -v

# Test only passing tests (skip integration tests)
uv run pytest tests/test_api_endpoints.py tests/test_search_tool.py tests/test_ai_generator.py -v

# Test MAX_RESULTS bug scenarios
uv run pytest tests/ -k "zero_results" -v

# Test with verbose output
uv run pytest tests/ -vv

# Test with debug output
uv run pytest tests/ -vv --log-cli-level=DEBUG

# Stop on first failure
uv run pytest tests/ -x
```

## Writing New Tests

### Basic Test Template
```python
def test_my_feature(fixture_name):
    """Test description"""
    # Setup
    result = fixture_name.some_method(param="value")

    # Assert
    assert result == expected_value
    assert "expected string" in result
```

### Using Fixtures
```python
def test_with_search_tool(course_search_tool):
    """Test uses pre-configured search tool"""
    result = course_search_tool.execute(query="testing")
    assert isinstance(result, str)
```

### Testing API Endpoints
```python
def test_api_endpoint(client, mock_rag_system):
    """Test HTTP endpoint with mocked backend"""
    response = client.post("/api/query", json={"query": "test"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    mock_rag_system.query.assert_called_once()
```

### Mocking Anthropic API
```python
@patch('anthropic.Anthropic')
def test_api_call(mock_anthropic_class, mock_anthropic_response):
    mock_client = Mock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = mock_anthropic_response("Answer")

    # Your test code here
```

## Test Data

### test_course.txt
Minimal course file with:
- Course metadata (title, link, instructor)
- 3 lessons (Getting Started, Unit Testing, Integration Testing)
- ~100 words per lesson
- Designed for fast, predictable tests

### Adding More Test Data
1. Create new `.txt` file in `tests/test_data/`
2. Follow format:
   ```
   Course Title: [title]
   Course Link: [url]
   Course Instructor: [name]

   Lesson 0: [title]
   Lesson Link: [url]
   [content]
   ```
3. Use in tests via fixture or direct loading

## Debugging Failed Tests

### View Full Traceback
```bash
uv run pytest tests/ -vv --tb=long
```

### Run Single Test
```bash
uv run pytest tests/test_search_tool.py::TestCourseSearchToolExecution::test_search_with_valid_query -vv
```

### Print Debug Info
```python
def test_debug(course_search_tool):
    result = course_search_tool.execute(query="test")
    print(f"Result: {result}")  # Will show in output with -s flag
    assert True
```

Run with:
```bash
uv run pytest tests/ -s  # -s shows print statements
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: astral-sh/setup-uv@v1
      - run: uv sync
      - run: uv run pytest tests/ -v
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
cd backend
uv run pytest tests/ -x
```

## Performance

### Test Execution Time
- Full suite: ~6 seconds
- Search tool tests: ~3 seconds
- AI generator tests: ~1 second
- Integration tests: ~2 seconds

### Optimization Tips
- Use temporary ChromaDB (already done in fixtures)
- Small test datasets (already done)
- Mock external APIs (needed for integration tests)
- Run tests in parallel: `pytest -n auto` (requires pytest-xdist)

## Troubleshooting

### Import Errors
**Problem**: `ModuleNotFoundError: No module named 'X'`
**Solution**: Run `uv sync` to install dependencies

### ChromaDB Errors
**Problem**: ChromaDB persistence errors
**Solution**: Tests use temporary directories, cleanup automatic

### API Key Errors
**Problem**: 401 authentication errors in integration tests
**Solution**: These are expected - tests need API mocking added

### Fixture Not Found
**Problem**: `fixture 'X' not found`
**Solution**: Check `conftest.py` - fixture may need to be added

## Contributing

### Adding New Tests
1. Identify component to test
2. Create test class in appropriate file
3. Use existing fixtures when possible
4. Follow naming convention: `test_<what>_<expected>`
5. Add docstrings explaining what's tested
6. Run tests to verify: `uv run pytest tests/ -v`

### Test Naming
- Test files: `test_<component>.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<behavior>_<scenario>`

### Good Test Practices
- ✅ Test one thing per test
- ✅ Use descriptive names
- ✅ Add docstrings
- ✅ Use fixtures for setup
- ✅ Assert specific values, not just truthiness
- ❌ Don't test implementation details
- ❌ Don't make tests depend on each other
- ❌ Don't use real external services

## Documentation

- **TEST_RESULTS.md** - Detailed test results and failure analysis
- **FIXES_SUMMARY.md** - Bugs found, fixes applied, impact analysis
- **This README** - How to run, write, and understand tests

## Questions?

For issues with:
- **Test failures** - Check TEST_RESULTS.md
- **System bugs** - Check FIXES_SUMMARY.md
- **Running tests** - Check this README
- **Writing tests** - Check pytest documentation: https://docs.pytest.org/
