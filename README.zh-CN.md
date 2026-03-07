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
  <a href="https://github.com/oGYCo/agent-loop/releases"><img src="https://img.shields.io/github/v/release/oGYCo/agent-loop?display_name=tag" alt="Version" /></a>
</p>

<p align="center">
  <a href="#快速开始"><strong>快速开始</strong></a> ·
  <a href="#cli-命令参考"><strong>CLI 参考</strong></a> ·
  <a href="#配置"><strong>配置</strong></a>
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

| 特性             | 描述                                             |
| ---------------- | ------------------------------------------------ |
| **实时流式输出** | AI 决策过程和工具调用的实时显示                  |
| **会话管理**     | 支持会话恢复、分支和检查点                       |
| **Hook 机制**    | PreToolUse、PostToolUse、Notification、Stop 钩子 |
| **人工干预**     | 错误阈值超出时自动暂停                           |
| **Git 集成**     | 每次会话后自动提交版本控制                       |
| **任务重试**     | 可配置的任务失败重试机制                         |
| **性能监控**     | 跟踪任务执行时间、会话时长和资源使用             |
| **配置热重载**   | 支持手动或文件监控方式重新加载配置               |
| **优雅关闭**     | 安全处理 SIGINT/SIGTERM 信号                     |
| **自动审查**     | 任务完成后自动进行任务计划审查                   |

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
python main.py init

# 运行 Agent（默认 10 次迭代）
python main.py run

# 指定迭代次数
python main.py run --iterations 3
```

## CLI 命令参考

```bash
# 核心命令
python main.py init                          # 初始化项目结构
python main.py run                           # 启动 Agent 循环（默认 10 次迭代）
python main.py run --iterations N           # 运行 N 次迭代
python main.py list                         # 列出所有任务
python main.py status                       # 显示项目状态
python main.py add "任务名称" -d "描述" -p 1 # 添加新任务

# 选项
python main.py --project-dir /path          # 指定项目目录
python main.py --help                       # 显示帮助信息
```

### 命令详情

| 命令     | 快捷方式 | 描述                              |
| -------- | -------- | --------------------------------- |
| `init`   | `--init` | 初始化项目并创建配置文件          |
| `run`    | `--run`  | 启动 Agent 循环（默认 10 次迭代） |
| `list`   |          | 列出所有任务及其状态和优先级      |
| `status` |          | 显示项目状态、Git 信息和任务统计  |
| `add`    |          | 添加新任务到功能列表              |

### Add 命令选项

```bash
# 添加带所有选项的任务
python main.py add "添加用户认证" -d "实现登录/登出" -p 1 --id "feat-101"

# 仅添加名称的任务（优先级默认为 3）
python main.py add "新功能"
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
| `session_manager.py`     | 会话生命周期管理，上下文管理，历史记录 |
| `state_manager.py`       | 状态持久化到 JSON，配置验证            |
| `task_selector.py`       | 基于优先级的任务选择                   |
| `human_intervention.py`  | 错误阈值监控，干预触发                 |
| `git_helper.py`          | Git 操作封装，自动提交                 |
| `test_runner.py`         | 测试执行封装                           |
| `performance_monitor.py` | 性能指标跟踪                           |
| `config_reloader.py`     | 配置热重载                             |

## 使用示例

### 基本工作流

```bash
# 1. 初始化项目
python main.py init

# 2. 查看现有任务
python main.py list

# 3. 运行 Agent
python main.py run --iterations 5

# 4. 查看状态
python main.py status
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
python main.py --project-dir /path/to/project run --iterations 3

# 查看特定项目状态
python main.py --project-dir /path/to/project status

# 列出其他项目的任务
python main.py --project-dir /path/to/project list
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
  "project_name": "agent-loop",
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
  "session_type": "coder"
}
```

### 配置选项

| 选项                             | 类型   | 描述                     |
| -------------------------------- | ------ | ------------------------ |
| `max_errors_before_intervention` | 整数   | 触发人工干预前的错误次数 |
| `retry.max_retries`              | 整数   | 任务失败后的最大重试次数 |
| `retry.retry_interval`           | 整数   | 重试间隔秒数             |
| `context_window_limit`           | 整数   | 上下文窗口的 Token 限制  |
| `model`                          | 字符串 | 使用的模型名称           |

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

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块
pytest tests/test_agent_core.py -v

# 带覆盖率
pytest tests/ --cov=agent --cov-report=term-missing

# 快速测试（快速失败）
pytest tests/ -x -q
```

## 项目结构

```
agent-loop/
├── agent/                      # 核心包
│   ├── __init__.py
│   ├── agent_core.py           # 核心 Agent 逻辑
│   ├── session_manager.py      # 会话管理
│   ├── state_manager.py        # 状态持久化
│   ├── task_selector.py        # 任务选择
│   ├── human_intervention.py   # 人工干预
│   ├── git_helper.py           # Git 操作
│   ├── test_runner.py          # 测试执行
│   ├── performance_monitor.py  # 性能跟踪
│   └── config_reloader.py      # 配置热重载
├── tests/                      # 单元测试
│   ├── test_agent_core.py
│   ├── test_state_manager.py
│   ├── test_task_selector.py
│   └── ...
├── main.py                     # CLI 入口点
├── pyproject.toml              # 项目配置 (uv)
├── README.md                   # 英文文档
├── README.zh-CN.md             # 中文文档
└── .agent/                    # 配置目录
    ├── config.json             # 项目配置
    ├── feature_list.json       # 任务列表
    ├── state.json              # 当前状态
    ├── session_history.json    # 会话历史
    └── MEMORY.md              # 经验积累
```

## 文档链接

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK 参考](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks 指南](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [流式输出](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [会话管理](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP 协议](https://modelcontextprotocol.io/introduction)

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
