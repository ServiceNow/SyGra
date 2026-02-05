import os
import time
import ast
import yaml
import uuid
from threading import Thread
from pathvalidate import is_valid_filename
from flask import Flask, request, jsonify
import shutil

from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.logger.logger_config import configure_logger, logger
from sygra.core.models.custom_models import ModelParams
from sygra.core.models.model_factory import ModelFactory
from sygra.utils import utils
from sygra.utils.dotenv import load_dotenv

# Fix SSL retry errors
CURL_CA_BUNDLE = os.environ.get("CURL_CA_BUNDLE", "")
REQUESTS_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", "")
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

load_dotenv(dotenv_path=".env", override=True)

app = Flask(__name__)

# Storage for tracking job status
jobs = {}

# Maximum chunk size for file processing (in bytes)
MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB


def check_model_availability(task_name):
    """Check if all required models for a task are available"""
    # Get all the models used in this task
    model_config_this_task = utils.get_models_used(task_name)

    # Import logger here since it needs to be configured first
    from sygra.logger.logger_config import logger

    # Test if all the models are active, else abort the process
    for mn, mc in model_config_this_task.items():
        if mc is None:
            logger.error(f"Model {mn} has no model configuration.")
            return False

        mc["name"] = mn
        # backend = mc.get("backend", "default")

        # Create model object for inference
        mod = ModelFactory.create_model(mc)
        model_param = ModelParams(url=mc.get("url"), auth_token=mc.get("auth_token"))

        # Check model availability
        status = mod.ping()
        if status != 200:
            logger.error(f"Model({mn}) is down.")
            return False

    logger.info("Required models are up and running.")
    return True


def extract_task_from_yaml(yaml_content):
    """Extract task name from YAML content"""
    try:
        # Parse YAML content
        yaml_data = yaml.safe_load(yaml_content)

        # Try to determine the task from the YAML structure
        # First check if it's directly specified
        if 'task' in yaml_data:
            return yaml_data['task']

        # If not directly specified, try to infer from directory structure or other clues
        # This is a heuristic approach and might need to be adjusted based on actual YAML structure
        # if 'graph_config' in yaml_data:
        #     # Look for patterns that might indicate the task
        #     yaml_str = str(yaml_data)
        #
        #     # Look for task-specific patterns in the YAML content
        #     for pattern in ['task_executor', 'tasks.']:
        #         if pattern in yaml_str:
        #             # Extract task name from the pattern (e.g., "tasks.task_name.something")
        #             parts = [p for p in yaml_str.split(pattern) if p]
        #             for part in parts:
        #                 task_candidate = part.split('.')[0].strip()
        #                 if task_candidate and not task_candidate.startswith(('_', '{')):
        #                     return task_candidate

        # If we can't determine the task, return a default or None
        return None
    except Exception as e:
        print(f"Error extracting task from YAML: {str(e)}")
        return None


def create_temp_task_directory(job_id, yaml_content):
    """Create a temporary directory for the task and save the YAML file"""

    cur_dir = os.path.join(os.getcwd())
    # Determine the task name or use the job_id if not found
    task_name = extract_task_from_yaml(yaml_content) or f"temp_task_{job_id}"

    # Create task directory structure
    task_specific_dir = os.path.join(cur_dir, "tasks", task_name)
    os.makedirs(task_specific_dir, exist_ok=True)

    # Save the YAML file
    yaml_path = os.path.join(task_specific_dir, "graph_config.yaml")
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    return task_name, task_specific_dir


def clean_temp_directory(task_dir):
    """Clean up temporary directory"""
    try:
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
    except Exception as e:
        print(f"Error cleaning temporary directory: {str(e)}")


def update_conversation(conversation, custom_prompt):
    # Extract updated system and user prompts if present
    updated_system = next((msg["system"] for msg in custom_prompt if "system" in msg), None)
    updated_user = next((msg["user"] for msg in custom_prompt if "user" in msg), None)

    # Prepare final updated conversation
    new_convo = []

    # Add system prompt at the beginning
    if updated_system:
        new_convo.append({"system": updated_system})
    else:
        # Retain original system prompt if it exists
        for msg in conversation:
            if "system" in msg:
                new_convo.append(msg)
                break  # Only one system message is expected

    # Process user message
    for msg in conversation:
        if "user" in msg:
            if updated_user and updated_user != msg["user"]:
                new_convo.append({"user": updated_user})
            else:
                new_convo.append(msg)
            break  # Only one user message expected

    return new_convo


def create_custom_prompt_task(original_task_name, custom_prompts, job_id):
    """Create a new task by copying and patching the graph_config.yaml of an existing task

    Args:
        original_task_name (str): Name of the original task
        custom_prompts (dict): Dictionary with node names as keys and prompts as values
        job_id (str): Unique identifier for the job

    Returns:
        tuple: (new_task_name, patched_yaml_content)
    """

    # Generate a new task name with UUID
    new_task_name = f"{original_task_name}_custom_{job_id}"
    # Get the original task's graph config file path
    cur_dir = os.path.join(os.getcwd())
    original_task_dir = os.path.join(cur_dir, "tasks", original_task_name)
    original_yaml_path = os.path.join(original_task_dir, "graph_config.yaml")

    if not os.path.exists(original_yaml_path):
        raise FileNotFoundError(f"Graph configuration file not found for task: {original_task_name}")

    # Read the original YAML file
    with open(original_yaml_path, 'r') as f:
        yaml_content = f.read()

    # Parse the YAML content
    config = yaml.safe_load(yaml_content)

    # update the prompts in the graph configuration
    updated_nodes = []
    if 'graph_config' in config and 'nodes' in config['graph_config']:
        nodes = config['graph_config']['nodes']
        for node_name, custom_prompt in custom_prompts.items():
            if node_name in nodes:
                if nodes[node_name]["node_type"] == "llm":
                    # Update the prompt in the node configuration
                    if 'prompt' not in nodes[node_name]:
                        nodes[node_name]['prompt'] = []
                    nodes[node_name]['prompt'] = update_conversation(nodes[node_name]['prompt'], custom_prompt)
                    updated_nodes.append(node_name)
                    logger.info(f"Updated custom prompt for node: {node_name}")
                elif nodes[node_name]["node_type"] == "weighted_sampler":
                    attributes = nodes[node_name].get("attributes", {})
                    for item in custom_prompt:
                        for key, values in item.items():
                            if key in attributes and 'values' in attributes[key]:
                                attributes[key]['values'] = values
            else:
                logger.warning(f"Warning: Node {node_name} not found in graph configuration")

    # Create new task directory
    new_task_dir = os.path.join(cur_dir, "tasks", new_task_name)
    os.makedirs(new_task_dir, exist_ok=True)

    # Convert back to YAML
    updated_yaml = yaml.dump(config, default_flow_style=False)

    # Save the patched YAML to the new task directory
    new_yaml_path = os.path.join(new_task_dir, "graph_config.yaml")
    with open(new_yaml_path, 'w') as f:
        f.write(updated_yaml)

    return new_task_name, updated_yaml, updated_nodes


def run_sygra_task(job_id, args, yaml_content=None):
    """Run a sygra task with the given arguments"""
    start = time.time()
    task_name = args.get("task")
    temp_dir = None

    # Update job status
    jobs[job_id]["status"] = "running"

    try:
        # Initialize logger
        debug = args.get("debug", False)
        clear_logs = args.get("clear_logs", False)
        run_name = args.get("run_name", "")
        configure_logger(debug, clear_logs, run_name)

        # Import logger after configuration
        from sygra.logger.logger_config import logger
        # If YAML content is provided, create temporary task directory
        if yaml_content:
            task_name, temp_dir = create_temp_task_directory(job_id, yaml_content)
            logger.info(f"Task name extracted from YAML: {task_name}")
            logger.info(f"Temporary task directory created: {temp_dir}")

            args["task"] = task_name
            jobs[job_id]["task"] = task_name

        logger.info("------------------------------------")
        logger.info(f"STARTING SYNTHESIS FOR TASK: {task_name}")
        logger.info("------------------------------------")
        logger.info(f"API ARGS: {args}")

        try:
            if run_name:
                assert is_valid_filename(run_name), f"Invalid run name: {run_name}"

            output_dir = args.get("output_dir")
            if output_dir:
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                logger.info(f"Output directory set to: {output_dir}")

            # Check models are available
            if not check_model_availability(task_name):
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = "Model not available"
                return

            # Preserve the current task name to use it in future
            utils.current_task = task_name

            specialized_executor_cls = None
            executor_path = f"{task_name}.task_executor.TaskExecutor"
            try:
                specialized_executor_cls = utils.get_func_from_str(executor_path)
                logger.info(f"Found specialized TaskExecutor at {executor_path}")
            except (ModuleNotFoundError, AttributeError) as e:
                logger.info(f"No specialized TaskExecutor found for task: {task_name}. Using DefaultTaskExecutor.")

            task_executor = specialized_executor_cls or DefaultTaskExecutor

            # Create an object similar to argparse's Namespace
            class Args:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            arg_obj = Args(**args)

            logger.info(f"Running {task_executor} for task {task_name}")
            task_executor(arg_obj).execute()

            logger.info("------------------------------------")
            logger.info(
                f"SYNTHESIS COMPLETE FOR TASK: {task_name} IN {(time.time() - start):0.2f} secs"
            )
            logger.info("------------------------------------")

            # Update job status to completed
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["duration"] = time.time() - start

        except Exception as e:
            logger.error(f"Error running task: {str(e)}")
            # Update job status to failed
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)

    finally:
        # Clean up temporary directory if it was created
        # if temp_dir:
        #     clean_temp_directory(temp_dir)

        # Reset environment variables
        os.environ["CURL_CA_BUNDLE"] = CURL_CA_BUNDLE
        os.environ["REQUESTS_CA_BUNDLE"] = REQUESTS_CA_BUNDLE


@app.route('/sygra/submit', methods=['POST'])
def submit_task():
    """API endpoint to submit a sygra task with traditional parameters"""
    data = request.json

    # Validate required parameters
    if not data.get('task'):
        return jsonify({'error': 'Task name is required'}), 400

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Process input parameters (with defaults matching main.py)
    task_args = {
        "task": data.get('task'),
        "start_index": int(data.get('start_index', 0)),
        "num_records": int(data.get('num_records', 5)),
        "batch_size": int(data.get('batch_size', 25)),
        "checkpoint_interval": int(data.get('checkpoint_interval', 100)),
        "debug": ast.literal_eval(str(data.get('debug', False))),
        "clear_logs": ast.literal_eval(str(data.get('clear_logs', False))),
        "output_with_ts": ast.literal_eval(str(data.get('output_with_ts', True))),
        "run_name": data.get('run_name', ''),
        "run_args": data.get('run_args', {}),
        "resume": ast.literal_eval(str(data.get('resume', 'None'))),
        "output_dir": data.get('output_dir'),
        "oasst": bool(data.get('oasst', False)),
        "quality": bool(data.get('quality', False))
    }

    # Initialize job status
    jobs[job_id] = {
        "status": "submitted",
        "task": task_args["task"],
        "submitted_at": time.time(),
        "args": task_args
    }

    # Run task in a separate thread
    thread = Thread(target=run_sygra_task, args=(job_id, task_args))
    thread.start()

    return jsonify({
        'message': 'Task submitted successfully',
        'job_id': job_id
    })


@app.route('/sygra/submit-yaml', methods=['POST'])
def submit_yaml_task():
    """API endpoint to submit a sygra task using YAML configuration"""
    # Check if YAML file is uploaded
    yaml_content = None
    data = request.json

    if 'file' in request.files:
        # Handle file upload
        file = request.files['file']
        if file and file.filename.endswith(('.yaml', '.yml')):
            yaml_content = file.read().decode('utf-8')
    elif request.is_json and 'yaml_content' in data:
        # Handle YAML content in request body
        yaml_content = data['yaml_content']
    else:
        # Check if the entire request body is YAML
        try:
            content_type = request.headers.get('Content-Type', '')
            if 'yaml' in content_type.lower() or 'yml' in content_type.lower():
                yaml_content = request.data.decode('utf-8')
            else:
                # Try to parse the request body as YAML
                request_data = request.get_data(as_text=True)
                # Simple validation to check if it looks like YAML
                if ':' in request_data and not request_data.strip().startswith('{'):
                    yaml_content = request_data
        except Exception:
            pass

    if not yaml_content:
        return jsonify({'error': 'No YAML configuration provided'}), 400

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Default arguments
    task_args = {
        "start_index": int(data.get('start_index', 0)),
        "num_records": int(data.get('num_records', 5)),
        "batch_size": int(data.get('batch_size', 25)),
        "checkpoint_interval": int(data.get('checkpoint_interval', 100)),
        "debug": ast.literal_eval(str(data.get('debug', False))),
        "clear_logs": ast.literal_eval(str(data.get('clear_logs', False))),
        "output_with_ts": ast.literal_eval(str(data.get('output_with_ts', True))),
        "run_name": f"yaml_job_{job_id}",
        "run_args": data.get('run_args', {}),
        "resume": ast.literal_eval(str(data.get('resume', 'None'))),
        "output_dir": data.get('output_dir'),
        "oasst": bool(data.get('oasst', False)),
        "quality": bool(data.get('quality', False))
    }

    # Override defaults with any provided parameters
    if request.is_json and isinstance(request.json, dict):
        for key in task_args:
            if key in request.json:
                task_args[key] = request.json[key]

    # Initialize job status (task name will be determined in run_sygra_task)
    jobs[job_id] = {
        "status": "submitted",
        "task": "yaml_task",  # Placeholder
        "submitted_at": time.time(),
        "args": task_args
    }

    # Run task in a separate thread
    thread = Thread(target=run_sygra_task, args=(job_id, task_args, yaml_content))
    thread.start()

    return jsonify({
        'message': 'YAML task submitted successfully',
        'job_id': job_id
    })


@app.route('/sygra/submit-custom-yaml', methods=['POST'])
def submit_custom_yaml():
    """API endpoint to update custom prompts in a task's graph config and run the pipeline"""
    data = request.json

    # Validate required parameters
    if not data.get('task'):
        return jsonify({'error': 'Task name is required'}), 400

    if data.get('custom_prompts') is not None and not isinstance(data.get('custom_prompts'), dict):
        return jsonify(
            {'error': 'custom_prompts must be provided as a dict with node names as keys and prompts as values'}), 400

    original_task_name = data.get('task')
    custom_prompts = data.get('custom_prompts', {})

    try:
        # Generate unique job ID
        job_id = data.get("job_id", None) or str(uuid.uuid4())

        # Create a new task with patched prompts
        new_task_name, patched_yaml, updated_nodes = create_custom_prompt_task(original_task_name, custom_prompts,
                                                                               job_id)

        # Process input parameters (with defaults matching main.py)
        task_args = {
            "job_id": job_id,
            "task": new_task_name,  # Use the new task name
            "start_index": int(data.get('start_index', 0)),
            "num_records": int(data.get('num_records', 5)),
            "batch_size": int(data.get('batch_size', 25)),
            "checkpoint_interval": int(data.get('checkpoint_interval', 100)),
            "debug": ast.literal_eval(str(data.get('debug', False))),
            "clear_logs": ast.literal_eval(str(data.get('clear_logs', False))),
            "output_with_ts": ast.literal_eval(str(data.get('output_with_ts', True))),
            "run_name": data.get('run_name', f"patched_{new_task_name}"),
            "run_args": data.get('run_args', {}),
            "resume": ast.literal_eval(str(data.get('resume', 'None'))),
            "output_dir": data.get('output_dir'),
            "oasst": bool(data.get('oasst', False)),
            "quality": bool(data.get('quality', False))
        }

        # Initialize job status
        jobs[job_id] = {
            "status": "submitted",
            "original_task": original_task_name,
            "task": new_task_name,
            "submitted_at": time.time(),
            "args": task_args,
            "updated_nodes": updated_nodes
        }

        # Run task in a separate thread
        thread = Thread(target=run_sygra_task, args=(job_id, task_args))
        thread.start()

        return jsonify({
            'message': 'Task with custom prompts submitted successfully',
            'job_id': job_id,
            'original_task': original_task_name,
            'new_task': new_task_name,
            'updated_nodes': updated_nodes
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'Error patching prompts: {str(e)}'}), 500


@app.route('/sygra/jobs', methods=['GET'])
def list_jobs():
    """List all jobs and their statuses"""
    return jsonify(jobs)


@app.route('/sygra/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a specific job"""
    if job_id in jobs:
        return jsonify(jobs[job_id])
    else:
        return jsonify({'error': 'Job not found'}), 404


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    # Add command-line arguments for the service
    import argparse

    parser = argparse.ArgumentParser(description='sygra Flask Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the service on')
    parser.add_argument('--port', type=int, default=8888, help='Port to run the service on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')

    service_args = parser.parse_args()

    # Start the Flask app
    app.run(host=service_args.host, port=service_args.port, debug=service_args.debug)
