# External AI Agent Repositories

This directory contains references to key open-source AI agent frameworks and tools integrated into the AGI Platform.

## Repositories

### 1. RedteamAgent
- **URL**: https://github.com/NeoTheCapt/RedteamAgent
- **Language**: Python
- **Description**: An AI red-team agent for authorized labs and web app pentesting workflows. Turns Claude Code / OpenCode / Codex into a structured recon → test → exploit → report workflow.
- **Topics**: AI agents, offensive security, penetration testing, LLM agents
- **Stars**: 115

### 2. OpenHands
- **URL**: https://github.com/OpenHands/OpenHands
- **Language**: TypeScript
- **Description**: 🙌 OpenHands: AI-Driven Development platform
- **Topics**: AI-Driven Development, artificial intelligence, LLM, ChatGPT, Claude AI
- **Stars**: 84,485
- **License**: MIT

### 3. TencentDB-Agent-Memory
- **URL**: https://github.com/TencentCloud/TencentDB-Agent-Memory
- **Language**: TypeScript
- **Description**: TencentDB Agent Memory is a team-level memory hub for AI Agents — turning conversations, docs, and code into four reusable memory assets (Chat Memory, Skill, LLM-Wiki, Code-Graph) that are governed, shared, and equipped across agents and frameworks.
- **Topics**: AI agents, embedding, LLM, memory, vector search
- **Stars**: 23,187

### 4. LangGraph
- **URL**: https://github.com/langchain-ai/langgraph
- **Language**: Python
- **Description**: Build resilient agents. A framework from LangChain for building multi-agent systems.
- **Topics**: Agents, AI, LLM, LangChain, multi-agent systems
- **Stars**: 40,025
- **License**: MIT

## How to Use

To initialize and fetch all submodules:

```bash
git clone --recurse-submodules https://github.com/kodikn/agi-platform.git
# or if already cloned
git submodule update --init --recursive
```

To update all submodules to latest:

```bash
git submodule foreach git pull origin main
```

## Integration Notes

- **RedteamAgent & LangGraph**: Python-based frameworks for agent development
- **OpenHands & TencentDB-Agent-Memory**: TypeScript-based platforms for agent orchestration and memory management
- All repositories are open-source and actively maintained
