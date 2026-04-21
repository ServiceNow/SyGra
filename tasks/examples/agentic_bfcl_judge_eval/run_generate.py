"""
Runner for generation-only pipeline (no judging).

Usage:
    python tasks/examples/agentic_bfcl_judge_eval/run_generate.py --difficulty easy
    python tasks/examples/agentic_bfcl_judge_eval/run_generate.py --difficulty hard --num_records 50
"""

import argparse
import ast
import json
import os
import time
from pathlib import Path

from pathvalidate import is_valid_filename

from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.logger.logger_config import configure_logger
from sygra.utils import utils
from sygra.utils.dotenv import load_dotenv

os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

load_dotenv(dotenv_path=".env", override=True)

TASK_NAME = "tasks.examples.agentic_bfcl_judge_eval"
DIR = Path(__file__).parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Generator model config key")
    parser.add_argument("--difficulty", required=True, choices=["easy", "medium", "hard"])
    parser.add_argument("--input", type=str, default=None, help="Override input file path")
    parser.add_argument("--num_records",        "-n",   type=int,              default=0)
    parser.add_argument("--batch_size",         "-b",   type=int,              default=25)
    parser.add_argument("--checkpoint_interval","-ci",  type=int,              default=500)
    parser.add_argument("--start_index",        "-si",  type=int,              default=0)
    parser.add_argument("--debug",              "-d",   type=ast.literal_eval, default=False)
    parser.add_argument("--clear_logs",         "-cl",  type=ast.literal_eval, default=False)
    parser.add_argument("--output_with_ts",     "-owt", type=ast.literal_eval, default=True)
    parser.add_argument("--run_name",           "-rn",  type=str,              default="")
    parser.add_argument("--run_args",           "-ra",  type=json.loads,       default={})
    parser.add_argument("--resume",             "-r",   type=ast.literal_eval, default=None)
    parser.add_argument("--output_dir",         "-od",  type=str,              default=None)
    parser.add_argument("--disable_metadata",   "-dm",  type=ast.literal_eval, default=False)
    parser.add_argument("--oasst",              "-ost", type=bool,             default=False)
    parser.add_argument("--quality",            "-q",   type=bool,             default=False)
    args = parser.parse_args()

    run_name = args.run_name or f"generate_{args.model}_{args.difficulty}"
    args.run_name = run_name
    args.task = TASK_NAME

    configure_logger(args.debug, args.clear_logs, run_name)
    from sygra.logger.logger_config import logger

    config = utils.load_yaml_file(filepath=str(DIR / "graph_config_generate_only.yaml"))

    # Patch model and input file
    config["graph_config"]["nodes"]["generate_tool_calls"]["model"]["name"] = args.model
    config["data_config"]["source"]["file_path"] = (
        args.input or f"tasks/examples/agentic_bfcl_judge_eval/input_{args.difficulty}.jsonl"
    )

    # Output to model-specific dir
    out_dir = str(DIR / args.model)
    os.makedirs(out_dir, exist_ok=True)
    args.output_dir = out_dir

    start = time.time()
    DefaultTaskExecutor(args, graph_config_dict=config).execute()
    logger.info(f"Done in {time.time() - start:.1f}s")
