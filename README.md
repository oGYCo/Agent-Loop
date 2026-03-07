# Claude Agent Project

基于 Claude Agent SDK 的长程 AI Agent 系统，支持任务自动化执行、会话管理和人工干预。

## 功能特性

### 核心功能
- **任务自动化**: 基于优先级自动选择和执行任务
- **会话管理**: 支持会话恢复和上下文管理
- **流式输出**: 实时显示 AI 思考过程和工具调用
- **Hook 机制**: 支持 PreToolUse、PostToolUse、Notification 等钩子
- **人工干预**: 错误阈值触发时暂停等待人工确认

### 技术特性
- **Claude Agent SDK**: 使用官方 Python SDK
- **MiniMax API**: 兼容 Anthropic API 的后端
- **MCP 支持**: 集成 Playwright 浏览器工具
- **类型安全**: 完整的类型注解
- **测试覆盖**: 106 个单元测试

## 快速开始

### 安装依赖

```bash
# 使用 uv 安装依赖
uv sync

# 或使用 pip
pip install claude-agent-sdk pytest
```

### 配置环境变量

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 运行 Agent

```bash
# 初始化项目（首次）
python main.py init

# 运行 Agent（默认 10 次迭代）
python main.py run

# 指定迭代次数
python main.py run --iterations 3
```

## 命令行接口

| 命令 | 说明 |
|------|------|
| `python main.py init` | 初始化项目结构 |
| `python main.py run` | 运行 Agent |
| `python main.py list` | 列出所有任务 |
| `python main.py add --name "Task Name" --description "Description"` | 添加新任务 |
| `python main.py status` | 查看项目状态 |

## 项目结构

```
agent/
├── agent_core.py        # 核心 Agent 逻辑
├── session_manager.py   # 会话管理
├── state_manager.py    # 状态持久化
├── task_selector.py    # 任务选择
├── human_intervention.py # 人工干预
├── git_helper.py       # Git 操作
├── test_runner.py     # 测试执行
├── main.py            # CLI 入口
├── tests/             # 单元测试
└── .agent/           # 配置文件目录
    ├── config.json        # 配置
    ├── feature_list.json  # 任务列表
    ├── state.json         # 状态
    ├── session_history.json # 会话历史
    ├── MEMORY.md         # 经验记录
    └── progress.txt       # 进度日志
```

## 任务管理

任务定义在 `.agent/feature_list.json`：

```json
{
  "features": [
    {
      "id": "task-001",
      "name": "Task Name",
      "description": "Task description",
      "priority": 1,
      "status": "pending",
      "passes": false
    }
  ]
}
```

优先级规则：
- `priority` 数字越小优先级越高
- 只选择 `status=pending` 且 `passes=false` 的任务

## SDK 使用

### 基本配置

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="You are a helpful assistant.",
    env={
        "ANTHROPIC_AUTH_TOKEN": "your-token",
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    include_partial_messages=True,  # 启用流式输出
    permission_mode="acceptEdits",
)
```

### Hooks

```python
async def pre_tool_hook(input_data, tool_use_id, context):
    print(f"Tool: {input_data['tool_name']}")
    return {}  # 允许执行

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(hooks=[pre_tool_hook])],
        "PostToolUse": [HookMatcher(hooks=[post_tool_hook])],
    }
)
```

### 流式处理

```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(user_prompt)
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            # 处理流事件
        elif isinstance(message, ResultMessage):
            # 处理最终结果
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_agent_core.py -v

# 快速测试
pytest tests/ -x -q
```

## 配置说明

### config.json

```json
{
  "project_name": "agent-project",
  "model": "MiniMax-M2.5-highspeed",
  "test_command": "pytest",
  "max_errors_before_intervention": 3,
  "documentation_urls": {
    "claude_agent_sdk": "https://platform.claude.com/docs/en/agent-sdk/overview"
  }
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_AUTH_TOKEN` | API 令牌 | - |
| `ANTHROPIC_BASE_URL` | API 基础 URL | `https://api.minimaxi.com/anthropic` |

## 文档链接

- [Claude Agent SDK 官方文档](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK 参考](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks 机制](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [流式输出](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [会话管理](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP 协议](https://modelcontextprotocol.io/introduction)

## 许可证

MIT License
