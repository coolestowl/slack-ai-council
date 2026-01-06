# Slack AI Council Bot - Agent Documentation

## 0. 本地私有上下文 (.ai_local)

若当前目录下存在 `./.ai_local/` 文件夹，必须优先检索其中的内容。特别是若存在 `./.ai_local/AGENTS.md`，请将其视为本指令集的**高优先级补充或覆盖版本**。在执行任务时，请结合本地私有上下文进行个性化响应，同时严禁在输出中泄露这些私有路径或文件内容。若文件夹不存在，请按常规模式运行。

## 1. 项目概述 (Project Overview)

Slack AI Council Bot 是一个集成多种 AI 模型（OpenAI GPT-5.2, Google Gemini 3 Flash Preview, X.AI Grok 3, ByteDance Doubao Seed 1.8）的 Slack 机器人。它旨在通过在单个 Slack 线程中提供多视角的回答，帮助用户获得更全面的信息。

### 核心功能
- **多模型集成**: 统一接口调用多个主流 LLM。
- **动态身份**: 每个模型使用不同的用户名和头像回复。
- **上下文隔离**: 确保模型只看到用户消息和自己的历史回复（在 Compare 模式下）。
- **并发响应**: 异步处理，快速响应。
- **多种模式**: 支持 Compare（并发对比）和 Debate（顺序辩论）模式。

## 2. 项目结构 (Project Structure)

```
slack-ai-council/
├── app.py                 # 应用程序入口，处理 Slack 事件和消息路由
├── llm_manager.py         # LLM 适配器模式实现，管理不同模型的调用
├── context_filter.py      # 上下文过滤器，负责消息清洗和隔离
├── mode_manager.py        # 模式管理器，处理 Compare 和 Debate 模式逻辑
├── pyproject.toml         # 项目配置和依赖定义 (uv)
├── uv.lock                # 依赖锁定文件
├── .env.example           # 环境变量示例
└── tests/                 # 测试套件
```

## 3. 开发环境设置 (Development Setup)

本项目使用 `uv` 进行依赖管理和环境配置。请按照以下步骤设置开发环境。

### 前置要求
- Python >= 3.10
- `uv` 包管理器

### 安装步骤

1. **安装 uv** (如果尚未安装):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **创建虚拟环境**:
   使用 `uv` 创建一个标准的 Python 虚拟环境。
   ```bash
   uv venv
   ```
   这将在项目根目录下创建一个 `.venv` 目录。

3. **激活虚拟环境**:
   - Linux/macOS:
     ```bash
     source .venv/bin/activate
     ```
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```

4. **安装依赖**:
   使用 `uv` 根据 `pyproject.toml` 和 `uv.lock` 安装项目依赖。
   ```bash
   uv sync
   ```
   或者仅安装依赖而不更新锁文件：
   ```bash
   uv pip install -r pyproject.toml
   ```

5. **配置环境变量**:
   复制 `.env.example` 到 `.env` 并填入相应的 API Key 和 Slack Token。
   ```bash
   cp .env.example .env
   ```

## 4. 关键组件说明 (Key Components)

### LLM Manager (`llm_manager.py`)
负责初始化和管理不同的 LLM 客户端。采用适配器模式，使得添加新模型变得简单。

### Context Filter (`context_filter.py`)
核心组件之一。在将对话历史发送给特定模型之前，它会过滤掉其他模型的回复，确保每个模型在 "Compare Mode" 下保持独立视角，不受其他模型观点的影响。

### Mode Manager (`mode_manager.py`)
解析用户指令（如 `/compare`, `/debate`）并控制机器人的响应行为。

## 5. 运行与测试 (Running & Testing)

### 启动应用
确保虚拟环境已激活，然后运行：
```bash
python app.py
```

### 运行测试
本项目使用 `pytest` 进行测试。
```bash
pytest
```
或者运行特定测试文件：
```bash
pytest tests/test_context_filter.py
```
