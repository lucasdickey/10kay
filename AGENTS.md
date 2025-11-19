# Claude Code Agents - 10KAY Project Guide

This document explains how to use Claude Code agents for various tasks in the 10KAY project, eliminating the need to repeatedly query the codebase.

## Available Agents & When to Use

### 1. General-Purpose Agent
**When to use:** Multi-step research, code exploration, understanding complex components

**Example tasks:**
- "Explore the current pipeline and understand the data flow"
- "Find all API endpoints and understand their parameters"
- "Research how user authentication works in this app"

**Why use instead of direct file reading:**
- Automatically searches across multiple files
- Synthesizes information from scattered code
- Saves context by exploring once and returning comprehensive summary
- Great for "how does X work" questions

---

### 2. Explore Agent (FAST MODE)
**When to use:** Quick pattern matching, file discovery, specific code location

**Example tasks:**
- "Find all TypeScript files in src/components"
- "Search for all database queries"
- "Find where the API endpoints are defined"

**Use modes:**
- `quick`: Basic searches, file finding (default)
- `medium`: Moderate exploration across multiple locations
- `very thorough`: Comprehensive analysis, naming convention variations

**Why use instead of Bash grep/find:**
- Much faster for glob patterns
- Returns context-aware results
- Better permission handling
- Optimized for code discovery

---

### 3. StatusLine-Setup Agent
**When to use:** Configuring Claude Code status line display

**Example tasks:**
- "Set up status line to show git branch"
- "Configure status line for my workflow"

---

## 10KAY Project - Specific Agent Recommendations

### For Pipeline-Related Questions

**USE: General-Purpose Agent with this prompt:**
```
Explore the 10KAY pipeline and explain:
1. What are the four phases? (Fetch, Analyze, Generate, Publish)
2. What commands run each phase?
3. What database tables are involved?
4. How does Claude AI integration work (Bedrock)?
5. What are the environment requirements?

Synthesize a complete overview so I never need to ask again.
```

**Result:** You'll get comprehensive understanding without repeatedly exploring files.

---

### For Code Location Questions

**USE: Explore Agent (quick mode)**
```
Find:
1. All Python pipeline files (fetch, analyze, generate, publish)
2. All Next.js API routes in app/api/*
3. Database migration files
4. Configuration files
```

**Result:** Fast mapping of codebase structure.

---

### For Understanding New Features

**USE: General-Purpose Agent**
```
I want to add [feature] to 10KAY. Help me understand:
1. Where would the code go?
2. What existing patterns should I follow?
3. What database changes are needed?
4. How does it integrate with the pipeline?
5. Are there similar features I can reference?

Search the codebase and synthesize a complete implementation guide.
```

**Result:** Clear implementation roadmap without repeated file reads.

---

## Command Reference for Common Tasks

### Task: "Add 50 new companies and run full pipeline"

```
Agent: General-Purpose
Prompt: "I have 50 new company tickers. How do I:
1. Add them to companies.json?
2. Seed them to the database?
3. Fetch their latest 10-K/10-Q filings?
4. Run analysis on all filings?
5. Generate content and publish?

Walk me through the exact commands and any data structures I need to understand."
```

---

### Task: "Fix an issue with the fetch phase"

```
Agent: Explore (medium)
Prompt: "The SEC EDGAR fetch phase is failing. Help me:
1. Find the edgar.py fetcher implementation
2. Show me the error handling code
3. What database table does it write to?
4. What are common failure scenarios?
5. Where is logging/debugging output?"
```

---

### Task: "Understand the Claude analysis system"

```
Agent: General-Purpose
Prompt: "Explain the Claude AI integration:
1. How does it connect to AWS Bedrock?
2. What sections of filings are extracted?
3. How is the prompt constructed?
4. What does the Claude response look like?
5. How is sentiment calculated?
6. How are bull/bear cases determined?"
```

---

### Task: "Set up CI/CD or deployment"

```
Agent: Explore (medium)
Prompt: "Find all deployment and CI/CD related files:
1. GitHub Actions workflows
2. Vercel configuration
3. Database migration scripts
4. Environment variable handling
5. Build and test scripts"
```

---

## Quick Reference: When NOT to Use Agents

- **Single file read:** Use `Read` tool directly
- **Editing one file:** Use `Edit` tool
- **Running commands:** Use `Bash` tool
- **Quick file search:** Use `Glob` tool if you know the pattern
- **Grep/search:** Use `Grep` tool for pattern matching
- **Git operations:** Use `Bash` with git commands

---

## 10KAY-Specific Knowledge Base (Pre-Explored)

This section documents what you should ask agents once to never repeat:

### ✅ Already Explored (See CLAUDE.md for details):

1. **Pipeline Architecture** ✓
   - 4 phases: Fetch → Analyze → Generate → Publish
   - SEC EDGAR integration (Phase 1)
   - Claude AI via Bedrock (Phase 2)
   - Email distribution via Resend (Phase 4)

2. **Database Schema** ✓
   - companies, filings, content, subscribers tables
   - Status flow: pending → analyzed → generated → published
   - JSONB metadata for flexible data storage

3. **Commands** ✓
   - `python3 pipeline/main.py --phase [fetch|analyze|generate|publish]`
   - `--tickers AAPL GOOGL` for specific companies
   - `--dry-run` for testing publish phase
   - `python3 seed_companies.py` for syncing

4. **Environment Variables** ✓
   - AWS credentials and region
   - Database URL
   - API keys: FINHUB, RESEND, BEDROCK
   - S3 bucket names

### ✅ Common Issues & Solutions (Pre-Documented):

| Issue | Solution | Location |
|-------|----------|----------|
| FINHUB_API_KEY missing | Add dummy key to .env.local | CLAUDE.md |
| SEC rate limiting | Auto-handled by fetcher | CLAUDE.md |
| Filing not in S3 | Check fetch phase status | CLAUDE.md |
| Claude analysis fails | Verify AWS credentials/model ID | CLAUDE.md |

---

## Pro Tips for Efficiency

### 1. Ask Comprehensive Questions to Agents
Instead of:
```
"How does the fetch phase work?"
```

Use:
```
"Explain the fetch phase including:
- What SEC API endpoints it calls
- How rate limiting works
- What gets stored in the database
- What file format the filings are in
- Common failure scenarios
So I have a complete understanding without asking again."
```

### 2. Request Actionable Summaries
Always ask agents to return:
- Exact commands to run
- Complete code examples
- Relevant file paths
- Links to implementation details

### 3. Use CLAUDE.md as Source of Truth
Before asking an agent, check if the answer is already in CLAUDE.md. The file is updated to include:
- Complete pipeline documentation
- Database schemas
- Command reference
- Troubleshooting guides

### 4. Explore in Batches
Instead of exploring one piece at a time, ask agents to explore entire subsystems:

**Good:** "Show me the complete file structure of the pipeline directory"
**Better:** "Map out all files in pipeline/, explain the data flow, show me how each phase integrates, give me all commands to run the full pipeline"

---

## Example: Complete New Feature Implementation

**Task:** Add support for 10-K/10-Q filings for a new company sector

**Step 1: Understand Current System** (Explore Agent)
```
Find all files related to:
1. Filing type handling (how 10-K vs 10-Q is distinguished)
2. Sector-specific analysis prompts
3. Company metadata storage
4. Filing categorization logic
```

**Step 2: Understand Requirements** (General-Purpose Agent)
```
Explain how to add support for a new filing type:
1. What database changes are needed?
2. How is filing type detected from SEC data?
3. Are there sector-specific Claude prompts?
4. How does the existing code differentiate 10-K from 10-Q?
5. What tests/validations are in place?
```

**Step 3: Implementation Guide** (General-Purpose Agent)
```
Based on the codebase, create a step-by-step guide to add [new filing type]:
1. Code changes needed in each pipeline phase
2. Database migrations required
3. Tests to write
4. Environment variables to add
5. Commands to test the new feature
```

**Result:** Complete implementation without repeatedly asking "how do I...?"

---

## Anti-Pattern: What NOT to Do

❌ **Don't:** Ask 10 separate questions about the pipeline
✅ **Do:** Ask one comprehensive question: "Explain the entire pipeline including all 4 phases, commands, database schema, and troubleshooting"

❌ **Don't:** Keep exploring the same files manually
✅ **Do:** Ask an agent to explore once and give complete overview

❌ **Don't:** Forget to reference CLAUDE.md
✅ **Do:** Check CLAUDE.md first, then ask agents for deep dives

❌ **Don't:** Ask vague questions ("How does X work?")
✅ **Do:** Be specific: "Explain X including: implementation details, failure scenarios, integration points, configuration options"

---

## Document Maintenance

This guide references CLAUDE.md. When CLAUDE.md is updated with new pipeline features:

1. Update the "Already Explored" section above
2. Add new troubleshooting issues to the table
3. Add new example agent prompts

**Goal:** Keep this as the "meta guide" for using agents effectively on this project.

---

## Quick Start: First Time?

1. Read CLAUDE.md - it has all the pre-explored information
2. Use this guide to understand when to ask agents vs reading docs
3. For a new feature: Use General-Purpose Agent with comprehensive prompt
4. For quick file finding: Use Explore Agent in quick mode
5. For detailed Q&A: Reference CLAUDE.md first, then ask agents

---

## Agent Prompts (Copy & Paste)

### Complete Pipeline Overview
```
Explain the 10KAY pipeline including:
1. What are all 4 phases and what does each do?
2. What commands run each phase?
3. How does Claude AI integration work?
4. What database tables are involved and their purpose?
5. What's the data flow from input to published analysis?
6. What environment variables are required?
7. How do you run it for specific companies?
8. What are common failure scenarios?

Return: Comprehensive overview, command examples, troubleshooting.
```

### Finding Code Patterns
```
Search the codebase for:
1. All SEC EDGAR API integration code
2. All Claude/Bedrock integration code
3. All database query patterns
4. All email distribution code

For each, show:
- File location
- Key functions
- Data structures used
- Integration points
```

### Understanding New Requirement
```
I need to [requirement]. Help me understand:
1. What existing code does similar things?
2. What patterns should I follow?
3. What database changes are needed?
4. How does it integrate with the pipeline?
5. Are there tests I should reference?
6. What's the complete implementation plan?
```
