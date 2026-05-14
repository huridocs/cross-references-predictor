# AGENTS.md - Agent Guidelines for cross-references-predictor

This file provides guidelines and commands for agentic coding agents operating in this repository.

## Code Style Guidelines

### General Rules
- **NO COMMENTS** - Never add code comments
- All imports must be at the top of the file
- Use Python 3.11+ type hints

### Type Hints
Always use type hints for function parameters and return types. Use lowercase types where possible (Python 3.9+):

Prefer `list`, `dict`, `set`, `tuple` over `List`, `Dict`, `Set`, `Tuple` from typing module.

### Classes
- Use Pydantic v2 `BaseModel` for data models
- Please, one class per file always

### Tech Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Package Manager**: mise, uv
- **Container**: Docker Compose
