# Architecture Overview

Understanding the system design and data flow of Agent-Loop.

## System Overview

Agent-Loop is a production-ready autonomous AI agent system that automates task execution using Claude Agent SDK with MiniMax API backend.

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        CLI[CLI Interface]
        API[REST API]
        WS[WebSocket]
    end

    subgraph "Agent Layer"
        AC[AgentCore]
        TS[TaskSelector]
        SM[SessionManager]
        ST[StateManager]
    end

    subgraph "Service Layer"
        GH[GitHelper]
        TR[TestRunner]
        PM[PerformanceMonitor]
        CR[ConfigReloader]
    end

    subgraph "Notification Layer"
        EN[EmailNotifier]
        SN[SlackNotifier]
        WH[Webhook]
    end

    subgraph "External"
        SDK[Claude SDK]
        API_EXT[MiniMax API]
    end

    CLI --> AC
    API --> AC
    WS --> AC

    AC --> TS
    AC --> SM
    AC --> ST

    AC --> GH
    AC --> TR
    AC --> PM
    AC --> CR

    AC --> SDK
    SDK --> API_EXT

    ST --> EN
    ST --> SN
    ST --> WH
```

## Core Components

### AgentCore (`agent/agent_core.py`)

The central orchestrator that coordinates all components.

```mermaid
graph LR
    A[Tasks] --> B[TaskSelector]
    B --> C[AgentCore]
    C --> D[Claude SDK]
    D --> E[Execute & Stream]
    E --> F[Process Results]
    F --> G[StateManager]
    G --> H[Notifications]
```

### Session Manager (`agent/session_manager.py`)

Manages agent sessions, context, and history.

```mermaid
sequenceDiagram
    participant User
    participant AgentCore
    participant SessionManager
    participant ClaudeSDK

    User->>AgentCore: Start execution
    AgentCore->>SessionManager: Create session
    SessionManager->>SessionManager: Initialize context
    AgentCore->>ClaudeSDK: Query with context
    ClaudeSDK-->>AgentCore: Stream results
    AgentCore->>SessionManager: Update session
    AgentCore-->>User: Display output
```

### State Manager (`agent/state_manager.py`)

Handles persistent state and configuration.

```mermaid
graph TD
    A[StateManager] --> B[Load State]
    A --> C[Save State]
    A --> D[Validate Config]
    A --> E[Watch Files]

    B --> F[.agent/state.json]
    C --> F
    D --> G[Schema Validation]
    E --> H[config.json]
```

### Notification System

```mermaid
graph LR
    subgraph "Events"
        T1[task_completed]
        T2[task_failed]
        T3[human_intervention]
    end

    subgraph "Router"
        NR[NotificationRouter]
    end

    subgraph "Providers"
        EN[Email]
        SN[Slack]
        WH[Webhook]
    end

    T1 --> NR
    T2 --> NR
    T3 --> NR

    NR --> EN
    NR --> SN
    NR --> WH
```

## Data Flow

### Task Execution Flow

```mermaid
flowchart TD
    A[Start Run] --> B{Select Task}
    B -->|No tasks| Z[Exit]
    B -->|Task found| C[Create Session]

    C --> D[Build Prompt]
    D --> E[Query Claude SDK]

    E --> F{Streaming Response}
    F -->|Tool Use| G[Execute Tool]
    G --> E
    F -->|Message| H[Process Message]

    H --> I{Error?}
    I -->|Yes| J[Increment Error Count]
    J --> K{Threshold?}
    K -->|Yes| L[Trigger Intervention]
    K -->|No| E
    I -->|No| M[Complete Task]

    M --> N[Save State]
    N --> O[Send Notifications]
    O --> P{Next Iteration?}
    P -->|Yes| B
    P -->|No| Z
```

### Configuration Reload Flow

```mermaid
flowchart LR
    A[File Change] --> B[ConfigReloader]
    B --> C[Load Config]
    C --> D[Validate Schema]
    D --> E[Hot Reload]
    E --> F[Notify Components]
```

## Module Dependencies

```mermaid
graph TD
    main[main.py] --> agent_core
    api[api.py] --> agent_core

    agent_core --> task_selector
    agent_core --> state_manager
    agent_core --> session_manager
    agent_core --> prompt_manager
    agent_core --> human_intervention
    agent_core --> config_reloader

    session_manager --> git_helper
    state_manager --> config_model

    task_selector --> state_manager

    human_intervention --> notification_queue
    notification_queue --> notification_router

    notification_router --> email_notifier
    notification_router --> slack_notifier
    notification_router --> webhook

    agent_core --> performance_monitor
    agent_core --> metrics
    agent_core --> logging_
```

## File Structure

```
agent/
├── __init__.py           # Package initialization
├── agent_core.py         # Core agent orchestration
├── config_model.py       # Pydantic config models
├── config_reloader.py    # Hot config reload
├── console.py            # CLI output formatting
├── constants.py          # Constants and enums
├── email_notifier.py     # Email notifications
├── exceptions.py        # Custom exceptions
├── git_helper.py         # Git operations
├── human_intervention.py # Intervention logic
├── logging_.py          # Structured logging
├── metrics.py            # Prometheus metrics
├── model_provider.py     # API provider abstraction
├── notification_queue.py # Async notification queue
├── notification_router.py# Event routing
├── performance_monitor.py# Performance tracking
├── prompt_manager.py    # Prompt templates
├── session_manager.py   # Session lifecycle
├── slack_notifier.py    # Slack notifications
├── state_manager.py     # State persistence
├── task_selector.py     # Task selection logic
├── test_runner.py       # Test execution
└── webhook.py           # Webhook notifications
```

## API Server Architecture

```mermaid
graph TB
    subgraph "FastAPI Server"
        HTTP[HTTP Endpoints]
        WS[WebSocket]
        MW[Middleware]
        CORS[CORS]
        GZIP[GZip]
    end

    subgraph "Routes"
        TASKS[Tasks API]
        RUN[Run API]
        STATUS[Status API]
        SESSION[Session API]
        METRICS[Metrics API]
        HEALTH[Health API]
    end

    subgraph "Services"
        SM[StateManager]
        TS[TaskSelector]
        SESSM[SessionManager]
    end

    MW --> HTTP
    MW --> WS
    CORS --> TASKS
    GZIP --> TASKS
    TASKS --> SM
    TASKS --> TS
    RUN --> SESSM
    STATUS --> SM
    METRICS --> SM
```

## Deployment Architecture

### Development Mode

```mermaid
graph LR
    User --> CLI[main.py]
    CLI --> SDK[MiniMax API]
```

### Production Mode (Docker)

```mermaid
graph TB
    subgraph "Docker Compose"
        LB[Reverse Proxy]
        API[agent-api]
        AGENT[agent-loop]
        PRO[Prometheus]
        GRAF[Grafana]
    end

    User --> LB
    LB --> API
    API --> AGENT
    AGENT --> SDK[MiniMax API]
    PRO --> AGENT
    GRAF --> PRO
```
