# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Retrieval-Augmented Generation (RAG) chatbot system for querying course materials. Users ask questions via a web UI, and the system uses semantic search (ChromaDB + Sentence Transformers) combined with Claude's tool-calling capabilities to provide answers with source citations.

**Tech Stack**: Python 3.13+, FastAPI, ChromaDB, Anthropic Claude API, Vanilla JS frontend, uv package manager

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Create .env file and add ANTHROPIC_API_KEY
cp .env.example .env
```

### Running the Application
```bash
# Quick start (from root)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8000
```

Application available at:
- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs

### Development
```bash
# Run with auto-reload (already enabled in run.sh)
cd backend && uv run uvicorn app:app --reload

# Clear vector database (forces rebuild on next start)
rm -rf backend/chroma_db
```

## Architecture Overview

### Request Flow (Tool-Based RAG Pattern)

The system uses a **two-stage Claude API pattern** where Claude decides whether to search, rather than automatically searching on every query:

```
User Query → FastAPI → RAG System → AI Generator → Claude API Call #1
                                                          ↓
                                             (Claude decides: "I need to search")
                                                          ↓
                                        Tool Execution (search_course_content)
                                                          ↓
                                        Vector Search (ChromaDB)
                                                          ↓
                                        Results → Claude API Call #2 → Synthesis
                                                          ↓
                                        Answer + Sources → User
```

**Key Pattern**: Claude makes TWO API calls per query that requires search:
1. First call: Claude receives the query + tool definitions, decides to use `search_course_content` tool
2. Tool executes: Semantic search in ChromaDB
3. Second call: Claude receives search results, synthesizes final answer

### Component Responsibilities

**RAGSystem** (`rag_system.py`): Main orchestrator
- Coordinates all components (document processor, vector store, AI generator, session manager)
- Manages query flow and conversation history
- Single entry point for query processing

**AIGenerator** (`ai_generator.py`): Claude API integration
- Handles tool-based response generation
- Manages two-stage API call pattern (initial → tool execution → synthesis)
- System prompt instructs Claude on tool usage: "Use search tool ONLY for course-specific questions"

**VectorStore** (`vector_store.py`): ChromaDB wrapper with two collections
- `course_catalog`: Course metadata (titles, instructors) for semantic course name matching
- `course_content`: Actual course text chunks for content search
- **Critical pattern**: Course name resolution via vector search (handles partial names like "MCP" → full title)

**DocumentProcessor** (`document_processor.py`): Text chunking
- Sentence-based splitting (800 chars, 100 overlap)
- Regex handles abbreviations correctly (`Dr.`, `U.S.`)
- Adds contextual prefixes: `"Course {title} Lesson {N} content: {chunk}"`

**ToolManager + CourseSearchTool** (`search_tools.py`): Tool interface
- Implements Anthropic's tool calling specification
- **Important**: `last_sources` stored on tool instance, retrieved after generation, then reset
- Tool execution flow: parse params → resolve course name → search → format → track sources

**SessionManager** (`session_manager.py`): Conversation context
- Stores last N exchanges (configurable via `MAX_HISTORY`, default 2)
- History formatted as string and injected into system prompt
- Sessions created lazily (only when first query arrives)

### Document Format Expected

Course files in `/docs` must follow this structure:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [lesson title]
Lesson Link: [url]
[lesson content...]

Lesson 1: [lesson title]
...
```

Metadata extraction uses regex matching (`process_course_document:97-146`). If no lesson markers found, entire document treated as single unit.

### Configuration

All settings in `config.py` with defaults:
- `CHUNK_SIZE`: 800 (characters per chunk)
- `CHUNK_OVERLAP`: 100 (overlap to prevent context loss)
- `MAX_RESULTS`: 5 (vector search results)
- `MAX_HISTORY`: 2 (conversation exchanges to remember)
- `EMBEDDING_MODEL`: "all-MiniLM-L6-v2"
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"

Change via environment variables or modify `config.py` dataclass.

### Data Models (`models.py`)

- **Course**: `title` (used as unique ID), `course_link`, `instructor`, `lessons[]`
- **Lesson**: `lesson_number`, `title`, `lesson_link`
- **CourseChunk**: `content`, `course_title`, `lesson_number`, `chunk_index`

Title serves as the course identifier throughout the system (ChromaDB IDs, filters, etc.).

### Critical Implementation Details

**Startup Sequence** (`app.py:88-98`):
- On FastAPI startup, automatically loads all `.txt`/`.pdf`/`.docx` files from `../docs`
- Checks existing course titles to avoid re-processing (deduplication)
- Creates embeddings and populates ChromaDB collections

**Course Name Resolution** (`vector_store.py:102-116`):
- User provides partial name → Vector search in `course_catalog` → Returns exact title
- Enables queries like "What's in the MCP course?" to match "Building Model Context Protocol"

**Source Tracking** (`search_tools.py:88-114`):
- Search results formatted with `[Course Title - Lesson N]` headers
- Sources stored in `tool.last_sources` array
- Retrieved via `tool_manager.get_last_sources()` after generation completes
- **Must call `reset_sources()` after retrieval** to avoid stale data

**Static File Serving** (`app.py:107-119`):
- Custom `DevStaticFiles` class adds no-cache headers for development
- Frontend mounted at root path `/`
- API routes at `/api/*`

### Common Modification Patterns

**Adding a New Tool**:
1. Create class inheriting from `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` (Anthropic format) and `execute(**kwargs)`
3. Register in `RAGSystem.__init__`: `self.tool_manager.register_tool(YourTool())`
4. Update `AIGenerator.SYSTEM_PROMPT` to instruct Claude on when to use it

**Changing Chunking Strategy**:
- Modify `DocumentProcessor.chunk_text()` (currently sentence-based)
- Adjust `CHUNK_SIZE` and `CHUNK_OVERLAP` in `config.py`
- Delete `chroma_db/` folder to force re-embedding

**Adjusting Search Behavior**:
- Modify `VectorStore.search()` for different filtering logic
- Change `MAX_RESULTS` in config for more/fewer search results
- Edit `CourseSearchTool._format_results()` for different result formatting

**Changing Conversation Memory**:
- Adjust `MAX_HISTORY` in config (number of Q&A exchanges, not individual messages)
- Modify `SessionManager.get_conversation_history()` for different formatting
- History injected into system prompt, so keep concise to avoid token bloat

### Frontend Architecture (`frontend/`)

Vanilla JavaScript with no build step:
- `script.js`: Handles API calls, message rendering (uses marked.js for markdown)
- `index.html`: Chat UI + sidebar with course stats
- `style.css`: Responsive layout

**Key Frontend Pattern**: Shows loading animation, replaces with response on completion. Session ID stored in `currentSessionId` and sent with each request.

## Notes

- **No tests currently exist** in this codebase
- ChromaDB data persists in `./backend/chroma_db` (gitignored)
- First request after startup may be slow (model loading)
- CORS enabled for all origins (development setting)
- Environment variables loaded via `python-dotenv` from `.env` file
- always use uv to run the server do not use pip directly
- use uv to run python files