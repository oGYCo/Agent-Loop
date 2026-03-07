# Agent-Loop

> 基于 Claude Agent SDK 构建的生产级自主 AI Agent 系统

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Agent-Loop 是一个自主 AI Agent 系统，通过实时可见性、会话管理和智能错误恢复实现任务自动化执行。基于 Claude Agent SDK 构建，支持 MiniMax API 后端。

## 核心特性

| 特性 | 描述 |
|------|------|
| **实时流式输出** | AI 决策过程和工具调用的实时显示 |
| **会话管理** | 支持会话恢复、分支和检查点 |
| **Hook 机制** | PreToolUse、PostToolUse、Notification、Stop 钩子 |
| **人工干预** | 错误阈值超出时自动暂停 |
| **Git 集成** | 每次会话后自动提交版本控制 |
| **MCP 支持** | 内置 Playwright 浏览器自动化 |

## 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/agent-loop.git
cd agent-loop

# 使用 uv 安装依赖
uv sync
```

### 2. 配置

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 3. 运行

```bash
# 初始化项目
python main.py init

# 运行 Agent（默认 10 次迭代）
python main.py run

# 指定迭代次数
python main.py run --iterations 3
```

## CLI 命令

```bash
python main.py init                    # 初始化项目结构
python main.py run                     # 启动 Agent 循环
python main.py run --iterations N     # 运行 N 次迭代
python main.py list                    # 列出所有任务
python main.py add --name "任务名" --description "描述" --priority 1
python main.py status                  # 显示项目状态
```

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                      CLI 入口                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     AgentCore                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │
│  │ TaskSelector │ │StateManager  │ │  GitHelper       │   │
│  └──────────────┘ └──────────────┘ └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 ClaudeSDKClient                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  流式输出 │ Hooks │ 会话管理 │ 文件检查点            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `agent_core.py` | Agent 核心逻辑，SDK 集成，任务执行 |
| `session_manager.py` | 会话生命周期管理 |
| `state_manager.py` | 状态持久化到 JSON |
| `task_selector.py` | 基于优先级的任务选择 |
| `human_intervention.py` | 错误阈值监控 |
| `git_helper.py` | Git 操作封装 |
| `test_runner.py` | 测试执行封装 |

## SDK 使用示例

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent, ResultMessage

# 配置流式输出和 Hooks
options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="You are a helpful coding assistant.",
    env={
        "ANTHROPIC_AUTH_TOKEN": "your-token",
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    include_partial_messages=True,
    permission_mode="acceptEdits",
)

# 执行任务并获取流式输出
async with ClaudeSDKClient(options=options) as client:
    await client.query("Write a hello world program")
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            # 处理流式事件
            pass
        elif isinstance(message, ResultMessage):
            print(f"Session: {message.session_id}")
```

## 任务管理

任务定义在 `.agent/feature_list.json`：

```json
{
  "features": [
    {
      "id": "feat-001",
      "name": "功能名称",
      "description": "功能描述",
      "priority": 1,
      "status": "pending",
      "passes": false
    }
  ]
}
```

- `priority` 数值越小，优先级越高
- 只选择 `status=pending` 且 `passes=false` 的任务

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块
pytest tests/test_agent_core.py -v

# 带覆盖率
pytest tests/ --cov=. --cov-report=term-missing
```

## 配置

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `ANTHROPIC_AUTH_TOKEN` | API 令牌 | 必填 |
| `ANTHROPIC_BASE_URL` | API 端点 | `https://api.minimaxi.com/anthropic` |

### config.json

```json
{
  "project_name": "agent-loop",
  "model": "MiniMax-M2.5-highspeed",
  "max_errors_before_intervention": 3,
  "test_command": "pytest"
}
```

## 文档

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK 参考](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks 指南](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [流式输出](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [会话管理](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP 协议](https://modelcontextprotocol.io/introduction)

## 项目结构

```
agent-loop/
├── agent_core.py           # 核心 Agent 逻辑
├── session_manager.py      # 会话管理
├── state_manager.py        # 状态持久化
├── task_selector.py        # 任务选择
├── human_intervention.py   # 人工干预
├── git_helper.py           # Git 操作
├── test_runner.py          # 测试执行
├── main.py                 # CLI 入口
├── tests/                  # 单元测试
├── pyproject.toml          # 项目配置 (uv)
├── README.md               # 英文文档
└── README.zh-CN.md        # 中文文档
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)。
