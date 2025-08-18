import logging
import os
from utils.constants import ROOT_DIR

log_dir = os.path.join(ROOT_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "out.log")
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s - %(levelname)s default - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file),
    ],
)
logger = logging.getLogger()


def configure_logger(debug_mode: bool, clear_logs: bool, run_name: str) -> None:
    global logger
    if not logger:
        if clear_logs and os.path.exists(log_file):
            os.remove(log_file)
        # create logs directory if not present
        if not os.path.exists("logs"):
            os.makedirs("logs")

        run_name_text = f" - {run_name}" if run_name else ""

        if debug_mode:
            openai_logger = logging.getLogger("openai")
            httpx_logger = logging.getLogger("httpx")
            openai_logger.setLevel(logging.DEBUG)
            httpx_logger.setLevel(logging.DEBUG)
            logging.basicConfig(
                level=logging.DEBUG,
                format=f"%(asctime)s - %(levelname)s{run_name_text} - %(message)s",
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file),
                ],
            )
        else:
            openai_logger = logging.getLogger("openai")
            httpx_logger = logging.getLogger("httpx")
            openai_logger.setLevel(logging.WARNING)
            httpx_logger.setLevel(logging.WARNING)
            logging.basicConfig(
                level=logging.INFO,
                format=f"%(asctime)s - %(levelname)s{run_name_text} - %(message)s",
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file),
                ],
            )
        logger = logging.getLogger()
