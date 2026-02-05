# sygra as a Service

This Flask-based service provides a RESTful API interface to the sygra pipeline. It allows you to trigger sygra tasks and monitor their progress through HTTP requests.

## Setup

1. Install the required dependencies:

```bash
pip install flask
```

2. Ensure your `.env` file is properly configured with all necessary environment variables for sygra.

## Running the Service

Start the service using the following command:

```bash
python sygra_service.py [--host HOST] [--port PORT] [--debug]
```

Arguments:
- `--host`: Host to run the service on (default: 0.0.0.0)
- `--port`: Port to run the service on (default: 8888)
- `--debug`: Run the service in debug mode

## API Endpoints

### 1. Submit a Task (Traditional Method)

**Endpoint**: `POST /sygra/submit`

**Request body**: JSON with the same parameters as sygra's main.py script:

```json
{
    "task": "your_task_name",  // Required
    "start_index": 0,          // Optional (default: 0)
    "num_records": 10,         // Optional (default: 10)
    "batch_size": 25,          // Optional (default: 25)
    "checkpoint_interval": 100, // Optional (default: 100)
    "debug": false,            // Optional (default: false)
    "clear_logs": false,       // Optional (default: false)
    "output_with_ts": true,    // Optional (default: true)
    "run_name": "",            // Optional (default: "")
    "run_args": {},            // Optional (default: {})
    "resume": null,            // Optional (default: null)
    "output_dir": null,        // Optional (default: null)
    "oasst": false,            // Optional (default: false)
    "quality": false           // Optional (default: false)
}
```

**Response**: JSON with job ID and status:

```json
{
    "message": "Task submitted successfully",
    "job_id": "unique-job-id"
}
```

### 2. Submit Task using YAML Configuration

**Endpoint**: `POST /sygra/submit-yaml`

This endpoint allows you to submit a task using a YAML configuration file (similar to graph_config.yaml) without having to specify the task name. The service will automatically extract task details from the YAML.

**Request Options**:

1. **YAML file upload**:
   ```
   Content-Type: multipart/form-data
   body: file=@path/to/your/graph_config.yaml
   ```

2. **YAML content in JSON**:
   ```json
   Content-Type: application/json
   body: {
     "yaml_content": "graph_config:\n  nodes:\n    extract_category: ..."
   }
   ```

3. **Raw YAML content**:
   ```
   Content-Type: application/x-yaml
   body: graph_config:
     nodes:
       extract_category:
        node_type: llm
        ...
   ```

You can also include additional parameters in the JSON body (for option 2) to override defaults:

```json
{
    "yaml_content": "your yaml content here",
    "num_records": 20,
    "debug": true
}
```

**Response**: Same as the traditional method.

### 3. List All Jobs

**Endpoint**: `GET /sygra/jobs`

**Response**: JSON with all jobs and their statuses.

### 4. Get Job Status

**Endpoint**: `GET /sygra/jobs/<job_id>`

**Response**: JSON with job status information:

```json
{
    "status": "running",  // Values: "submitted", "running", "completed", "failed"
    "task": "task_name",
    "submitted_at": 1689352487.123,
    "args": { /* task arguments */ }
}
```

For completed jobs, the response will also include a `duration` field.
For failed jobs, the response will include an `error` field with an error message.

### 5. Health Check

**Endpoint**: `GET /health`

**Response**: JSON indicating service health:

```json
{
    "status": "healthy"
}
```

### 6. Custom Prompts in Graph Configuration

The service provides an endpoint to use custom prompts in a task's graph configuration YAML and run the pipeline. Instead of modifying the original task, this endpoint creates a new task with a UUID-based name that contains the updated configuration.

```bash
curl -X POST http://localhost:8888/sygra/submit-custom-yaml \
  -H "Content-Type: application/json" \
  -d '{
    "task": "example_task",
    "custom_prompts": {
      "node_name_1": "Your patched prompt for node 1",
      "node_name_2": "Your patched prompt for node 2"
    }
  }'
```

**Required Parameters:**
- `task`: Name of the original task to base the new task on
- `custom_prompts`: Dictionary with node names as keys and prompt strings as values

**Optional Parameters:**
All standard parameters accepted by `/sygra/submit` are also valid here.

**Response:**
```json
{
  "job_id": "generated-uuid",
  "message": "Task with custom prompts submitted successfully",
  "original_task": "example_task",
  "new_task": "example_task_custom_a1b2c3d4",
  "updated_nodes": ["node_name_1", "node_name_2"]
}
```

This endpoint allows you to dynamically modify the prompts in specific nodes of a task's graph configuration by:
1. Creating a new task folder with a UUID-based name
2. Copying the original task's graph configuration
3. Updating the specified prompts in the configuration
4. Running the pipeline with this new task

The original task remains untouched, and each request creates a unique task.

## Example Usage

### 1. Starting a Task (Traditional Method)

```bash
curl -X POST http://localhost:8888/sygra/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task": "example_task",
    "num_records": 5,
    "debug": true
  }'
```

### 2. Submitting a YAML Configuration

```bash
# Upload a YAML file
curl -X POST http://localhost:8888/sygra/submit-yaml \
  -F "file=@path/to/your/graph_config.yaml"

# Or provide YAML content directly
curl -X POST http://localhost:8888/sygra/submit-yaml \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "graph_config:\n  nodes:\n    extract_category:\n     node_type: llm\n     ..."
  }'
```

### 4. Checking Job Status

```bash
curl http://localhost:8888/sygra/jobs/job-id-from-submit-response
```

### 5. Getting All Jobs

```bash
curl http://localhost:8888/sygra/jobs
```

## Important Notes

1. **Model Configuration**: The service uses model parameters default parameters in `config/models.yaml` and overwrites them with any parameters provided in `.env`. You do not need to specify model parameters in your API calls.

2. **YAML Task Execution**: When submitting a YAML configuration, the service will:
   - Extract the task name from the YAML content
   - Create a temporary task directory structure
   - Save the YAML as `graph_config.yaml` in the appropriate location
   - Execute the task using the sygra pipeline
   - Clean up temporary files after execution if needed

## Error Handling

- If a required parameter is missing, the service will return a 400 Bad Request response.
- If a job ID is not found, the service will return a 404 Not Found response.
- If a task execution fails, the job status will be set to "failed" with an error message.
