---
name: pinecone-help
description: Overview of all available Pinecone skills and what a user needs to get started. Invoke when a user asks what skills are available, how to get started with Pinecone, or what they need to set up before using any Pinecone skill.
---

# Pinecone Skills — Help & Overview

Pinecone is the leading vector database for building accurate and performant AI applications at scale in production. It's useful for building semantic search, retrieval augmented generation, recommendation systems, and agentic applications.

Here's everything you need to get started and a summary of all available skills.

<<invoke_any_skill>>

---

## What You Need

### Required
- **Pinecone account** — free to create at https://app.pinecone.io/?sessionType=signup
- **API key** — create one in the Pinecone console after signing up, then make it
  available to this environment:
  <<api_key_setup>>

### Optional (unlock more capabilities)

| Tool | What it enables | Install |
|---|---|---|
| **Pinecone MCP server** | Use Pinecone directly inside your AI agent/IDE without writing code | <<mcp_server_status>> |
| **Pinecone CLI (`pc`)** | Manage all index types from the terminal, batch operations, backups, CI/CD | `brew tap pinecone-io/tap && brew install pinecone-io/tap/pinecone` |
| **uv** | Run the packaged Python scripts included in these skills | [Install uv](https://docs.astral.sh/uv/getting-started/installation/) |

---

## Available Skills

| Skill | What it does |
|---|---|
| `pinecone-quickstart` | Step-by-step onboarding — create an index, upload data, and run your first search |
| `pinecone-query` | Search integrated indexes using natural language text via the Pinecone MCP |
| `pinecone-cli` | Use the Pinecone CLI (`pc`) for terminal-based index and vector management |
| `pinecone-assistant` | Create, manage, and chat with Pinecone Assistants for document Q&A with citations |
| `pinecone-mcp` | Reference for all Pinecone MCP server tools and their parameters |
<<help_row_full_text_search>>
| `pinecone-docs` | Curated links to official Pinecone documentation, organized by topic |
<<help_row_n8n>>

---

## Which skill should I use?

**Just getting started?** → `pinecone-quickstart`

**Want to search an index you already have?**
- Integrated index (built-in embedding model) → `pinecone-query` (uses MCP)
- Any other index type → `pinecone-cli`

**Working with documents and Q&A?** → `pinecone-assistant`

<<help_route_full_text_search>>

<<help_route_n8n>>

**Need to manage indexes, bulk upload vectors, or automate workflows?** → `pinecone-cli`

**Looking up API parameters or SDK usage?** → `pinecone-docs`

**Need to understand what MCP tools are available?** → `pinecone-mcp`
