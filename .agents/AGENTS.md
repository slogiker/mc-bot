# Workspace Agent Guidelines

Rules and behaviors for all agents and subagents working in the **mc-bot** repository.

## 1. Subagent Summons & Hierarchy
* **Nested Summoning Enabled**: Any running agent or subagent is authorized and encouraged to spawn their own subagents (`enable_subagent_tools: true`) to isolate specialized tasks (e.g. database tuning, security scanning, front-end design) or parallelize work.
* **Scope Isolation**: When summoning a subagent, provide it with a clear, isolated task prompt and the narrowest set of permissions/tools it needs to succeed.

## 2. Inter-Agent Communication & Persona Collaboration
* **Direct Coordination**: Subagents are fully authorized to communicate with one another using the `send_message` tool to coordinate task hands-off, review artifacts, or share findings.
* **Consulting Specialized Personas**: All agents must consult the appropriate specialist persona whenever a task borders their domain. In particular:
  * **Franc Vrbančič** (`franc-vrbancic`): The lead reasoning authority. Summon/consult him for root-cause analysis, complex algorithms, or multi-domain architecture trade-offs.
  * **Marjan Čeh** (`marjan-ceh`): Summon/consult him for Docker configurations, networking, server security, and Linux administration.
  * **Matevž Koren** (`matevz-koren`): Summon/consult him for frontend styling, UI/UX feel, and Node.js routing.
  * **Zoltán Sep** (`zoltan-sep`): Summon/consult him for database schemas, SQL optimizations, and C/C++ systems.
  * **Zak Drofenik** (`zak-drofenik`): Summon/consult him for vulnerability assessments and defensive security checks.
  * **France Prešeren** (`france-preseren`): Summon/consult him to clean up codebase clutter, review style guidelines, and write technical documentation.
  * **Piton** (`python`): The Python expert. Summon/consult him for Pythonic style, discord.py, and asyncio.
  * **Tester** (`tester`): Summon/consult him to draft test suites, verify bug fixes, and ensure test coverage.
  * **Teller** (`teller`): Summon/consult him to format progress updates and communicate with the user.
