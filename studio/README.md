# SyGra Studio

**Visual workflow builder and execution platform for SyGra synthetic data pipelines**

---

## Why This Exists

SyGra is a graph-oriented framework for building synthetic data generation pipelines using LLMs. While powerful, creating and debugging YAML-based workflow configurations requires deep familiarity with the schema and manual iteration.

**SyGra Studio** provides:
- A visual drag-and-drop interface for designing workflows
- Real-time execution monitoring with node-level progress
- Integrated code editing with syntax highlighting
- Data source preview and transformation testing
- Model management across multiple LLM providers

It replaces the manual YAML editing workflow with an interactive builder while maintaining full compatibility with the SyGra framework.

---

## Quickstart

### Using Make (Recommended)

```bash
# From repo root - one command does everything
make studio
```

This automatically builds the frontend (if needed) and starts the server at http://localhost:8000.

### Manual Setup

```bash
# 2. Build the frontend
cd studio/frontend
npm install
npm run build
cd ../..

# 3. Start the server
uv run python -m studio.server --tasks-dir ./tasks/examples --svelte

# 4. Open browser
# Navigate to http://localhost:8000
```

**Verification**: You should see the SyGra Studio interface with a sidebar listing available workflows from `tasks/examples/`.

---

## Features

| Feature | Description |
|---------|-------------|
| **Visual Graph Builder** | Drag-and-drop workflow creation with 12+ node types |
| **Multi-LLM Support** | Azure OpenAI, OpenAI, Ollama, vLLM, Mistral, Vertex AI, Bedrock |
| **Real-time Execution** | Live node status, logs, and output streaming |
| **Code Editor** | Monaco-based Python/YAML editing with syntax highlighting |
| **Data Preview** | Sample data loading with transformation preview |
| **Structured Outputs** | JSON schema validation for LLM responses |
| **Nested Workflows** | Subgraph support for modular workflow composition |
| **Execution History** | Full run tracking with comparison and analytics |
| **Export** | Generate production-ready YAML and Python code |

### Non-Goals

- Production job scheduler
- Multi-tenant platform
- Model training
- Distributed execution

---

## Installation

### Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.9, 3.10, 3.11 | 3.9.7 excluded due to bug |
| Node.js | 18+ | For frontend build |
| npm | 9+ | Package manager |

### Install from Source

```bash
# Clone repository
git clone https://github.com/ServiceNow/SyGra.git
cd SyGra

# Install Python dependencies
pip install -e .

# Build frontend
cd studio/frontend
npm install
npm run build
cd ../..
```

### Verify Installation

```bash
python -c "from studio import create_server; print('OK')"
```

---

## Configuration

### Environment Variables

Studio uses environment variables for model credentials and settings. Variables are stored in `studio/.env` and can be managed via the Settings UI.

### Model Credentials

Model credentials follow the pattern `SYGRA_{MODEL_NAME}_{URL|TOKEN}`:

```bash
# Azure OpenAI
SYGRA_GPT-4O_URL=https://your-resource.openai.azure.com/
SYGRA_GPT-4O_TOKEN=your-api-key

# vLLM / Self-hosted
SYGRA_LLAMA_3_1_8B_URL=http://localhost:8001/v1
SYGRA_LLAMA_3_1_8B_TOKEN=your-token

# Ollama (local)
SYGRA_QWEN3_URL=http://localhost:11434
```

### Custom Models

Add models to `studio/config/custom_models.yaml`:

```yaml
my_custom_model:
  type: azure_openai
  model_name: gpt-4o
  deployment_name: my-deployment
  api_version: "2024-02-15-preview"
  parameters:
    temperature: 0.7
    max_tokens: 4096
```

---

## Usage

### Make Commands (Recommended)

The project includes a Makefile with convenient commands for Studio. Run from the repository root:

| Command | Description |
|---------|-------------|
| `make studio` | Build frontend (if needed) and start server |
| `make studio-build` | Build frontend only (skips if already built) |
| `make studio-rebuild` | Force rebuild frontend |
| `make studio-dev` | Print instructions for development mode |
| `make studio-clean` | Remove frontend build artifacts and node_modules |

**Configuration via environment variables:**

```bash
# Custom tasks directory and port
make studio TASKS_DIR=./my/tasks PORT=9000

# Default values
# TASKS_DIR=./tasks/examples
# PORT=8000
```

### CLI Reference

```bash
python -m studio.server [OPTIONS]
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--tasks-dir` | `-t` | `None` | Directory containing workflow tasks |
| `--host` | `-H` | `0.0.0.0` | Host to bind |
| `--port` | `-p` | `8000` | Port to listen on |
| `--reload` | `-r` | `false` | Auto-reload on code changes |
| `--log-level` | `-l` | `info` | Logging level (debug/info/warning/error) |
| `--svelte` | `-s` | `false` | Use Svelte UI (requires build) |

### Examples

```bash
# Development with auto-reload
python -m studio.server -t ./tasks/examples --reload --svelte

# Production
python -m studio.server -t /opt/sygra/tasks -p 8080 --svelte

# Custom host binding
python -m studio.server -H 127.0.0.1 -p 3000 --svelte
```

### Programmatic Usage

```python
from studio import run_server, create_app

# Simple: run blocking server
run_server(tasks_dir="./tasks", port=8000, use_svelte_ui=True)

# Advanced: get FastAPI app for custom middleware
app = create_app(tasks_dir="./tasks")
# Add custom routes, middleware, etc.
```

---

## API Reference

### Workflow Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workflows` | List all workflows |
| `GET` | `/api/workflows/{id}` | Get workflow graph |
| `POST` | `/api/workflows` | Create workflow |
| `PUT` | `/api/workflows/{id}` | Update workflow |
| `DELETE` | `/api/workflows/{id}` | Delete workflow |
| `GET` | `/api/workflows/{id}/yaml` | Export as YAML |
| `PUT` | `/api/workflows/{id}/nodes/{node_id}` | Update node |
| `DELETE` | `/api/workflows/{id}/nodes/{node_id}` | Delete node |
| `POST` | `/api/workflows/{id}/edges` | Add edge |
| `DELETE` | `/api/workflows/{id}/edges/{edge_id}` | Delete edge |

### Execution Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/workflows/{id}/execute` | Start execution |
| `GET` | `/api/executions` | List executions (paginated) |
| `GET` | `/api/executions/{id}` | Get execution status |
| `POST` | `/api/executions/{id}/cancel` | Cancel execution |
| `DELETE` | `/api/executions/{id}` | Delete execution record |

### Model Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/models` | List configured models |
| `POST` | `/api/models/{name}/ping` | Health check model |
| `POST` | `/api/models/ping-all` | Health check all models |

### Execute Workflow Example

```bash
curl -X POST http://localhost:8000/api/workflows/my_workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": [{"question": "What is machine learning?"}],
    "num_records": 1,
    "batch_size": 25
  }'
```

Response:
```json
{
  "execution_id": "exec_abc123",
  "status": "running",
  "message": "Execution started"
}
```

### Poll Execution Status

```bash
curl http://localhost:8000/api/executions/exec_abc123
```

Response:
```json
{
  "id": "exec_abc123",
  "workflow_id": "my_workflow",
  "status": "completed",
  "started_at": "2026-01-19T10:30:00Z",
  "completed_at": "2026-01-19T10:30:45Z",
  "duration_ms": 45000,
  "node_states": {
    "llm_1": {"status": "completed", "duration_ms": 2500}
  },
  "output_data": [{"response": "Machine learning is..."}]
}
```

---

## Common Workflows

### Create a New Workflow

1. Click **"Create Workflow"** in the sidebar
2. Drag nodes from the palette onto the canvas
3. Connect nodes by dragging from output handle to input handle
4. Click each node to configure in the details panel
5. Click **"Save"** to generate YAML and Python files

### Add an LLM Node

1. Drag **"LLM"** node onto canvas
2. In details panel:
   - Set **Summary** (display name)
   - Select **Model** from dropdown
   - Add **System** and **User** prompts
   - Set **Output Key** for state variable
3. Connect to previous/next nodes

### Configure Structured Output

1. Select an LLM node
2. Enable **"Structured Output"**
3. Choose schema mode:
   - **Inline**: Define fields directly
   - **Class Path**: Reference a Pydantic model
4. Set fallback strategy (instruction/post_process)

### Preview Data Source

1. Select a **Data** node
2. Click **"Preview"** in the data panel
3. Configure source type (CSV, JSON, HuggingFace)
4. Set parameters (file path, repo ID, split)
5. Click **"Load Sample"** to preview rows

### Run a Workflow

1. Open Workflow
2. Click **"Run Workflow"** button
3. Configure execution parameters:
   - Number of records
   - Batch size
4. Click **"Run Workflow"**
5. Monitor progress in the Runs panel

---

## Operational Guide

### Execution Storage

Executions are stored in `studio/.executions/`:

```
.executions/
├── index.json          # Metadata index (loaded on startup)
└── runs/
    ├── exec_abc123.json
    ├── exec_def456.json
    └── ...
```

**Index refresh**: If the index becomes stale:
```bash
curl -X POST http://localhost:8000/api/executions/storage/refresh
```
