"""
Runner for agentic_bfcl_query_rewrite.

Usage:
    python tasks/examples/agentic_bfcl_query_rewrite/run.py [main.py args]
"""

import argparse
import ast
import json
import os
import sys
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

TASK_NAME = "tasks.examples.agentic_bfcl_query_rewrite"
DIR = Path(__file__).parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_records",        "-n",   type=int,             default=0)
    parser.add_argument("--batch_size",         "-b",   type=int,             default=25)
    parser.add_argument("--checkpoint_interval","-ci",  type=int,             default=500)
    parser.add_argument("--start_index",        "-si",  type=int,             default=0)
    parser.add_argument("--debug",              "-d",   type=ast.literal_eval, default=False)
    parser.add_argument("--clear_logs",         "-cl",  type=ast.literal_eval, default=False)
    parser.add_argument("--output_with_ts",     "-owt", type=ast.literal_eval, default=True)
    parser.add_argument("--run_name",           "-rn",  type=str,             default="rewrite")
    parser.add_argument("--run_args",           "-ra",  type=json.loads,      default={})
    parser.add_argument("--resume",             "-r",   type=ast.literal_eval, default=None)
    parser.add_argument("--output_dir",         "-od",  type=str,             default=None)
    parser.add_argument("--disable_metadata",   "-dm",  type=ast.literal_eval, default=False)
    parser.add_argument("--oasst",              "-ost", type=bool,            default=False)
    parser.add_argument("--quality",            "-q",   type=bool,            default=False)
    args = parser.parse_args()

    args.task = TASK_NAME

    configure_logger(args.debug, args.clear_logs, args.run_name)
    from sygra.logger.logger_config import logger

    config = utils.load_yaml_file(filepath=str(DIR / "graph_config.yaml"))

    if args.output_dir and not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    start = time.time()
    DefaultTaskExecutor(args, graph_config_dict=config).execute()
    logger.info(f"Done in {time.time() - start:.1f}s")
