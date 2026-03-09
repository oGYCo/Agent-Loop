<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="180" />
</p>

<h1 align="center">Agent-Loop</h1>

<p align="center">
  <em>基于 Claude Agent SDK 构建的生产级自主 AI Agent 系统</em>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://github.com/oGYCo/agent-loop/stargazers"><img src="https://img.shields.io/github/stars/oGYCo/agent-loop" alt="Stars" /></a>
</p>

<p align="center">
  <a href="#快速开始"><strong>快速开始</strong></a> ·
  <a href="#核心特性"><strong>核心特性</strong></a> ·
  <a href="#cli-命令参考"><strong>CLI 参考</strong></a> ·
  <a href="#docker-部署"><strong>Docker</strong></a> ·
  <a href="#配置"><strong>配置</strong></a> ·
  <a href="#api-文档"><strong>API 文档</strong></a> ·
  <a href="#常见问题"><strong>FAQ</strong></a> ·
  <a href="CONTRIBUTING.md"><strong>贡献指南</strong></a>
</p>

---

Agent-Loop 是一个自主 AI Agent 系统，通过实时流式输出、会话管理、智能错误恢复和性能监控实现任务自动化执行。基于 Claude Agent SDK 构建，使用 MiniMax API 作为后端。

## 为什么选择 Agent-Loop？

| 优势         | 描述                                   |
| ------------ | -------------------------------------- |
| **完全透明** | AI 决策过程和工具调用的实时流式显示    |
| **高可靠性** | 自动会话恢复、文件检查点和优雅关闭     |
| **可扩展**   | 强大的 Hook 机制，支持监控和自定义集成 |
| **自我改进** | 自动任务计划审查和文档优化             |
| **生产级**   | 类型安全、测试完善、文档齐全、性能监控 |

## 核心特性

| 特性                   | 描述                                                  |
| ---------------------- | ----------------------------------------------------- |
| **实时流式输出**       | AI 决策过程和工具调用的实时显示                       |
| **会话管理**           | 支持会话恢复、分支和检查点                            |
| **Hook 机制**          | PreToolUse、PostToolUse、Notification、Stop 钩子        |
| **人工干预**           | 错误阈值超出时自动暂停                                |
| **Git 集成**           | Agent 自主执行 git commit 和 push，每个任务后保存进度 |
| **任务重试**           | 可配置的任务失败重试机制                              |
| **性能监控**           | 跟踪任务执行时间、会话时长和资源使用                  |
| **配置热重载**         | 支持手动或文件监控方式重新加载配置                    |
| **优雅关闭**           | 安全处理 SIGINT/SIGTERM 信号                          |
| **自动审查**           | 任务完成后自动进行任务计划审查                        |
| **可定制提示词**       | 基于模板的提示词系统，支持 `{{variable}}` 变量替换    |
| **邮件通知**           | 任务完成、失败或干预时发送邮件提醒                    |
| **Webhook 通知**       | 向外部服务发送 HTTP POST 通知                         |
| **任务看板 UI**        | 可视化 Kanban 风格任务看板，支持拖拽                   |
| **API 密钥认证**       | 安全 API 访问，支持可配置 API 密钥                    |
| **Grafana 监控面板**   | 预置 Grafana 监控面板模板                             |
| **增强的错误处理**     | 改进的错误恢复和优雅降级                              |

## 快速开始

### 1. 克隆和安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/agent-loop.git
cd agent-loop

# 使用 uv 安装依赖
uv sync
```

### 2. 配置

创建 `.env` 文件或设置环境变量：

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 3. 运行

```bash
# 初始化项目（创建 .agent/ 目录）
uv run python main.py init

# 运行 Agent（默认 10 次迭代）
uv run python main.py run

# 指定迭代次数
uv run python main.py run --iterations 3
```

## CLI 命令参考

```bash
# 核心命令
uv run python main.py init                          # 初始化项目结构
uv run python main.py run                           # 启动 Agent 循环（默认 10 次迭代）
uv run python main.py run --iterations N           # 运行 N 次迭代
uv run python main.py list                         # 列出所有任务
uv run python main.py status                       # 显示项目状态
uv run python main.py add "任务名称" -d "描述" -p 1 # 添加新任务

# 提示词管理
uv run python main.py prompt list                  # 列出所有提示词预设
uv run python main.py prompt show <key>            # 显示提示词详情
uv run python main.py prompt set <key>             # 设置活跃提示词
uv run python main.py prompt add <key> -n "名称"   # 添加新的提示词预设
uv run python main.py prompt delete <key>          # 删除提示词预设

# 模板管理
uv run python main.py template list                # 列出所有模板
uv run python main.py template show <name>         # 显示模板内容
uv run python main.py template scaffold            # 导出所有模板到 .agent/prompt_templates/
uv run python main.py template reset <name>        # 重置模板为内置默认值

# 选项
uv run python main.py --project-dir /path          # 指定项目目录
uv run python main.py --help                       # 显示帮助信息
```

### 命令详情

| 命令     | 快捷方式 | 描述                              |
| -------- | -------- | --------------------------------- |
| `init`   | `--init` | 初始化项目并创建配置文件          |
| `run`    | `--run`  | 启动 Agent 循环（默认 10 次迭代） |
| `list`   |          | 列出所有任务及其状态和优先级      |
| `status` |          | 显示项目状态、Git 信息和任务统计  |
| `add`    |          | 添加新任务到功能列表              |
| `prompt` |          | 管理提示词预设 (list/show/set/add/delete) |
| `template` |        | 管理提示词模板 (list/show/scaffold/reset) |

### Add 命令选项

```bash
# 添加带所有选项的任务
uv run python main.py add "添加用户认证" -d "实现登录/登出" -p 1 --id "feat-101"

# 仅添加名称的任务（优先级默认为 3）
uv run python main.py add "新功能"
```

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                      CLI 入口点                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  信号处理 │ 参数解析 │ 命令分发                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AgentCore                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐ │
│  │TaskSelector │ │StateManager  │ │ PerformanceMonitor     │ │
│  ├──────────────┤ ├──────────────┤ ├────────────────────────┤ │
│  │SessionManager│ │  GitHelper   │ │  ConfigReloader      │ │
│  ├──────────────┤ ├──────────────┤ ├────────────────────────┤ │
│  │HumanInterven│ │AgentTestRunner│ │ ClaudeSDKClient      │ │
│  └──────────────┘ └──────────────┘ └────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ClaudeSDKClient                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  流式输出 │ Hooks │ 会话管理 │ 文件检查点               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="48" />
</p>

### 核心模块

| 模块                     | 职责                                   |
| ------------------------ | -------------------------------------- |
| `agent_core.py`          | Agent 核心逻辑，SDK 集成，任务执行     |
| `prompt_manager.py`      | 模板引擎、提示词预设、用户可覆盖模板   |
| `session_manager.py`     | 会话生命周期管理，上下文管理，历史记录 |
| `state_manager.py`       | 状态持久化到 JSON，配置验证            |
| `task_selector.py`       | 基于优先级的任务选择                   |
| `human_intervention.py`  | 错误阈值监控，干预触发                 |
| `git_helper.py`          | Git 操作封装，状态和分支管理           |
| `test_runner.py`         | 测试执行封装                           |
| `performance_monitor.py` | 性能指标跟踪                           |
| `config_reloader.py`     | 配置热重载                             |
| `config_model.py`        | Pydantic 配置模型，支持环境变量        |
| `constants.py`           | 集中式常量、配置键/路径的枚举         |
| `exceptions.py`          | 异常层次结构和错误码系统               |
| `model_provider.py`      | 多提供商支持 (OpenAI, Anthropic, MiniMax) |
| `metrics.py`             | Prometheus 指标收集和导出              |
| `logging_.py`            | structlog 结构化日志                  |
| `console.py`             | Rich 控制台工具，交互式 CLI 输出      |
| `webhook.py`             | Webhook 通知服务                      |
| `email_notifier.py`      | 邮件通知服务 (SMTP)                    |
| `slack_notifier.py`      | Slack 通知服务 (Block Kit)             |
| `notification_router.py` | 通知路由到适当渠道                    |
| `notification_queue.py`  | 异步通知队列，用于批处理              |

## 使用示例

### 基本工作流

```bash
# 1. 初始化项目
uv run python main.py init

# 2. 查看现有任务
uv run python main.py list

# 3. 运行 Agent
uv run python main.py run --iterations 5

# 4. 查看状态
uv run python main.py status
```

### 任务管理

任务定义在 `.agent/feature_list.json`：

```json
{
  "features": [
    {
      "id": "self-001",
      "name": "阅读项目文档",
      "description": "阅读 CLAUDE.md 和 README.md 了解项目",
      "priority": 1,
      "status": "pending",
      "passes": false,
      "verify_command": "cat CLAUDE.md | head -20",
      "context_files": ["CLAUDE.md", "README.md"],
      "created_at": "2026-03-07",
      "updated_at": "2026-03-07"
    }
  ]
}
```

**任务选择条件：**
- `status` 必须为 `"pending"`
- `passes` 必须为 `false`
- 按优先级选择任务（数值越小优先级越高）

### 自定义项目目录

```bash
# 在其他项目上运行 Agent
uv run python main.py --project-dir /path/to/project run --iterations 3

# 查看特定项目状态
uv run python main.py --project-dir /path/to/project status

# 列出其他项目的任务
uv run python main.py --project-dir /path/to/project list
```

## 配置

### 环境变量

| 变量                   | 描述         | 必填 | 默认值                               |
| ---------------------- | ------------ | ---- | ------------------------------------ |
| `ANTHROPIC_AUTH_TOKEN` | API 认证令牌 | 是   | -                                    |
| `ANTHROPIC_BASE_URL`   | API 端点 URL | 否   | `https://api.minimaxi.com/anthropic` |

### config.json

```json
{
  "project_name": "my-project",
  "project_type": "generic",
  "test_command": "pytest",
  "test_pattern": "test_*.py",
  "max_errors_before_intervention": 3,
  "retry": {
    "max_retries": 3,
    "retry_interval": 5,
    "retry_on_errors": ["connection_error", "timeout", "process_error"]
  },
  "context_window_limit": 100000,
  "model": "MiniMax-M2.5-highspeed",
  "session_type": "coder",
  "context_files": ["README.md", "CLAUDE.md"],
  "verify_command": "uv run pytest tests/ -x -q",
  "allowed_tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
  "mcp_servers": []
}
```

### 配置选项

| 选项                             | 类型       | 描述                       |
| -------------------------------- | ---------- | -------------------------- |
| `project_name`                   | 字符串     | 提示词模板中使用的项目名称 |
| `max_errors_before_intervention` | 整数       | 触发人工干预前的错误次数   |
| `retry.max_retries`              | 整数       | 任务失败后的最大重试次数   |
| `retry.retry_interval`           | 整数       | 重试间隔秒数               |
| `context_window_limit`           | 整数       | 上下文窗口的 Token 限制    |
| `model`                          | 字符串     | 使用的模型名称             |
| `context_files`                  | 字符串数组 | 系统提示中包含的上下文文件 |
| `verify_command`                 | 字符串     | 任务完成后的验证命令       |
| `allowed_tools`                  | 字符串数组 | Agent 允许使用的 SDK 工具  |
| `mcp_servers`                    | 对象数组   | MCP 服务器配置             |

### 邮件配置

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "use_tls": true,
    "from_name": "Agent-Loop",
    "from_email": "agent-loop@example.com",
    "to_emails": ["admin@example.com", "team@example.com"],
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 30
  }
}
```

### Webhook 配置

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-server.com/webhook",
    "secret": "your-webhook-secret",
    "timeout": 10,
    "events": ["task_completed", "task_failed", "human_intervention"],
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

### API 密钥配置

```json
{
  "api_keys": {
    "enabled": true,
    "keys": ["your-api-key-1", "your-api-key-2"]
  }
}
```

## SDK 使用示例

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent, ResultMessage

# 配置流式输出和 Hooks
options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="You are a helpful coding assistant.",
    env={
        "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    include_partial_messages=True,
    permission_mode="acceptEdits",
    enable_file_checkpointing=True,
)

# 执行任务并获取流式输出
async with ClaudeSDKClient(options=options) as client:
    await client.query("Write a hello world program")
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            print(f"Event: {message.type}")
        elif isinstance(message, ResultMessage):
            print(f"Completed: {message.session_id}")
```

## 提示词定制

Agent-Loop 使用基于模板的提示词系统。所有提示词支持 `{{variable}}` 变量替换，并可完全自定义。

### 模板解析顺序

1. **用户覆盖**：`.agent/prompt_templates/<name>.md`（最高优先级）
2. **内置默认**：内嵌在源代码中（兜底）

### 可用模板

| 模板                | 描述                                   |
| ------------------- | -------------------------------------- |
| `system`            | 主系统提示（身份、工具、工作流）       |
| `task`              | 带项目上下文的任务执行提示             |
| `self_review`       | 任务完成后的计划审查提示               |
| `memory_cleanup`    | MEMORY.md 清理建议提示                 |
| `claude_md_cleanup` | CLAUDE.md 清理建议提示                 |

### 系统提示变体

| 变体         | 描述                             |
| ------------ | -------------------------------- |
| `default`    | 通用型自主 Agent                 |
| `coder`      | 专注软件开发                     |
| `researcher` | 专注研究和文档                   |
| `reviewer`   | 专注代码审查和质量保证           |

通过 config.json 中的 `session_type` 设置变体。

### 自定义模板

```bash
# 导出所有模板到 .agent/prompt_templates/
uv run python main.py template scaffold

# 编辑任意模板文件，例如：
# .agent/prompt_templates/system.md
# .agent/prompt_templates/task.md

# 模板中可用的变量：
# {{project_name}}       - 来自 config.json
# {{project_structure}}  - 自动扫描的项目目录树
# {{task_name}}          - 当前任务名称
# {{task_description}}   - 当前任务描述
# {{context_files_list}} - config 中 context_files 列出的文件
# {{current_date}}       - 今天的日期
# {{feature_list_path}}  - feature_list.json 的路径

# 重置模板为内置默认值
uv run python main.py template reset system
```

## 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 运行特定模块
uv run pytest tests/test_agent_core.py -v

# 带覆盖率
uv run pytest tests/ --cov=agent --cov-report=term-missing

# 快速测试（快速失败）
uv run pytest tests/ -x -q
```

## 项目结构

```
agent-loop/
├── agent/                      # 核心包
│   ├── __init__.py
│   ├── agent_core.py           # 核心 Agent 逻辑
│   ├── prompt_manager.py       # 模板引擎和提示词管理
│   ├── session_manager.py      # 会话管理
│   ├── state_manager.py        # 状态持久化
│   ├── task_selector.py        # 任务选择
│   ├── human_intervention.py   # 人工干预
│   ├── git_helper.py           # Git 操作
│   ├── test_runner.py          # 测试执行
│   ├── performance_monitor.py  # 性能跟踪
│   ├── config_reloader.py      # 配置热重载
│   ├── config_model.py         # Pydantic 配置模型
│   ├── constants.py            # 集中式常量与枚举
│   ├── exceptions.py           # 异常层次结构
│   ├── model_provider.py       # 多提供商支持
│   ├── metrics.py              # 指标收集
│   ├── logging_.py            # 结构化日志
│   ├── console.py              # 控制台 UI
│   ├── webhook.py              # Webhook 通知服务
│   ├── email_notifier.py       # 邮件通知服务
│   ├── slack_notifier.py       # Slack 通知服务
│   ├── notification_router.py  # 通知路由
│   └── notification_queue.py   # 异步通知队列
├── tests/                      # 单元测试
│   ├── test_agent_core.py
│   ├── test_state_manager.py
│   ├── test_task_selector.py
│   ├── test_email_notifier.py
│   ├── test_webhook.py
│   ├── test_slack_notifier.py
│   ├── test_notification_router.py
│   └── ...
├── dashboards/                  # Grafana 监控面板模板
│   └── agent-loop-dashboard.json
├── static/                     # Web 看板静态文件
│   └── index.html
├── api.py                      # REST API 服务
├── main.py                     # CLI 入口点
├── pyproject.toml              # 项目配置 (uv)
├── README.md                   # 英文文档
├── README.zh-CN.md             # 中文文档
└── .agent/                    # 配置目录
    ├── config.json             # 项目配置
    ├── feature_list.json       # 任务列表
    ├── prompts.json            # 提示词预设
    ├── state.json              # 当前状态
    ├── session_history.json    # 会话历史
    ├── MEMORY.md               # 经验积累
    └── prompt_templates/       # 用户可自定义的提示词模板
        ├── system.md
        ├── task.md
        └── ...
```

## 文档链接

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK 参考](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks 指南](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [流式输出](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [会话管理](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP 协议](https://modelcontextprotocol.io/introduction)

---

## API 文档

Agent-Loop 提供 RESTful API 用于程序化访问 Agent 操作、任务管理和监控。

### 快速启动

```bash
# 启动 API 服务器
uv run python api.py

# 访问交互式 API 文档
# 在浏览器中打开 http://localhost:8000/docs
```

### API 端点概览

| 端点 | 方法 | 描述 |
| -------- | ------ | ----------- |
| /tasks | GET | 列出所有任务 |
| /run | POST | 启动 Agent 执行 |
| /tasks | GET/POST | 列出或创建任务 |
| /tasks/{id} | GET/PATCH/DELETE | 管理单个任务 |
| /status | GET | 获取当前 Agent 状态 |
| /session/history | GET | 获取会话历史 |
| /metrics | GET | Prometheus 指标端点 |
| /health | GET | 健康检查端点 |

完整的 API 文档和请求/响应示例，请参阅 [API 参考指南](docs/api-reference.md)。

---

## 常见问题

### 常见问题解答

#### Q: 如何开始使用 Agent-Loop？

A: 按照我们的 [快速开始](#快速开始) 指南：
1. 克隆仓库
2. 运行 `uv sync` 安装依赖
3. 通过环境变量设置 API 凭证
4. 运行 `uv run python main.py init` 初始化
5. 运行 `uv run python main.py run` 启动 Agent

#### Q: 我需要哪些 API 凭证？

A: Agent-Loop 需要：
- `ANTHROPIC_AUTH_TOKEN` - 用于认证的 API 令牌
- `ANTHROPIC_BASE_URL` - API 端点（默认为 MiniMax API）

#### Q: 如何配置通知？

A: 请参阅 [通知设置指南](docs/notification-setup.md) 了解配置详情：
- 邮件通知 (SMTP)
- Slack Webhook
- 自定义 Webhook

#### Q: 可以在 Docker 中运行 Agent-Loop 吗？

A: 可以！请参阅 [Docker 部署](#docker-部署) 部分：
- 单容器部署
- Docker Compose 完整栈
- Prometheus 和 Grafana 集成

#### Q: 如何自定义 Agent 提示词？

A: 使用模板系统：
```bash
# 导出所有模板
uv run python main.py template scaffold

# 在 .agent/prompt_templates/ 中编辑模板
# 重置为默认
uv run python main.py template reset system
```

更多详情请参阅 [提示词定制](#提示词定制)。

#### Q: 如果 Agent 遇到错误会发生什么？

A: Agent-Loop 内置错误处理：
1. 可配置重试次数的自动重试
2. 用于恢复的会话检查点
3. 错误阈值超过时触发人工干预
4. 详细日志用于调试

#### Q: 如何与现有项目集成？

A: 使用 `--project-dir` 标志：
```bash
uv run python main.py --project-dir /path/to/your/project run
```

#### Q: 在哪里可以找到 API 文档？

A: 启动 API 服务器并访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 贡献

我们欢迎贡献！请参阅我们的 [贡献指南](CONTRIBUTING.md) 了解：
- 开发环境设置
- 代码风格指南
- Pull Request 流程
- 测试要求

---

<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="64" />
</p>

<p align="center">
  <strong>Agent-Loop</strong> · 基于 Claude Agent SDK 构建
</p>

<p align="center">
  <a href="https://github.com/oGYCo/agent-loop">GitHub</a> ·
  <a href="https://github.com/oGYCo/agent-loop/issues">问题反馈</a> ·
  <a href="https://github.com/oGYCo/agent-loop/blob/main/LICENSE">许可证</a>
</p>
