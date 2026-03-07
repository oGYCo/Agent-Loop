#!/bin/bash
# Environment Initialization Script
# 长程AI Agent环境初始化脚本

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "Initializing AI Agent Environment..."
echo "Project root: $PROJECT_ROOT"

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

echo "Python version: $(python3 --version)"

# 检查并创建虚拟环境（可选）
if [ -d "venv" ]; then
    echo "Using existing virtual environment..."
    source venv/bin/activate
elif [ ! -f "requirements.txt" ]; then
    # 创建虚拟环境
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 安装依赖（如果有）
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# 初始化Agent配置
echo "Initializing Agent configuration..."
python3 main.py init

# 初始化Git仓库
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
    git add -A
    git commit -m "Initial commit: AI Agent project setup"
fi

echo ""
echo "========================================="
echo "Initialization Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .agent/feature_list.json to add tasks"
echo "  2. Run 'python main.py list' to see tasks"
echo "  3. Run 'python main.py run' to start the agent"
echo ""
