import asyncio
import json
import math
import os
from typing import Any

import aiohttp
import numpy as np
import pandas as pd
from tqdm import tqdm

from sygra.utils import utils


def create_dir(path: str):
    os.makedirs(path, exist_ok=True)


class LogProbModel:
    """
    Async client for TGI or vLLM, managing its own aiohttp session.
    """

    def __init__(self, cfg: dict[str, Any]):
        self.type = cfg["model_type"]
        self.url = cfg["url"].rstrip("/") if isinstance(cfg["url"], str) else cfg["url"]
        self.name = cfg.get("model_serving_name")
        self.auth = cfg.get("auth_token")
        self.timeout = cfg.get("timeout_seconds", 120)
        self.max_retries = cfg.get("max_retries", 3)
        self.session: aiohttp.ClientSession | None = None
        self.call_counter = 0

        # Support for multiple endpoints
        if isinstance(self.url, list):
            self.urls = self.url
            self.auths = self.auth if isinstance(self.auth, list) else [self.auth] * len(self.urls)
            self.url = self.urls[0]  # Default to first one
            self.auth = self.auths[0]
        else:
            self.urls = [self.url]
            self.auths = [self.auth]

    async def __aenter__(self):
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        self.session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    def _get_endpoint_index(self):
        if len(self.urls) == 1:
            return 0
        idx = self.call_counter % len(self.urls)
        self.call_counter += 1
        return idx

    async def generate(self, prompt: str) -> list[float]:
        # Get endpoint based on round-robin
        endpoint_idx = self._get_endpoint_index()
        current_url = self.urls[endpoint_idx]
        current_auth = self.auths[endpoint_idx]

        # Update session headers if auth token changed
        if current_auth and current_auth != self.auth:
            self.auth = current_auth
            if self.session:
                self.session._default_headers["Authorization"] = current_auth

        retry_count = 0
        while retry_count < self.max_retries:
            try:
                if self.type == "tgi":
                    endpoint = f"{current_url}/generate"
                    body = {
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 1,
                            "return_full_text": True,
                            "details": True,
                            "decoder_input_details": True,
                        },
                    }
                else:  # vllm
                    endpoint = f"{current_url}/completions"
                    body = {
                        "model": self.name,
                        "prompt": prompt,
                        "max_tokens": 1,
                        "prompt_logprobs": 0,
                    }

                resp = await self.session.post(endpoint, json=body, timeout=self.timeout)

                # Handle error status codes
                if resp.status == 429:
                    retry_count += 1
                    await asyncio.sleep(2**retry_count)  # Exponential backoff
                    continue
                elif resp.status >= 400 and resp.status < 500 or resp.status >= 500:
                    retry_count += 1
                    if retry_count < self.max_retries:
                        # Try next endpoint if available
                        if len(self.urls) > 1:
                            endpoint_idx = (endpoint_idx + 1) % len(self.urls)
                            current_url = self.urls[endpoint_idx]
                            current_auth = self.auths[endpoint_idx]
                            if self.session and current_auth:
                                self.session._default_headers["Authorization"] = current_auth
                        await asyncio.sleep(0.5)
                        continue

                resp.raise_for_status()
                data = await resp.json()

                if self.type == "tgi":
                    return [e["logprob"] for e in data["details"]["prefill"]]
                return data["choices"][0]["prompt_logprobs"]

            except (aiohttp.ClientError, asyncio.TimeoutError):
                retry_count += 1
                if retry_count >= self.max_retries:
                    raise
                await asyncio.sleep(0.5)

        raise RuntimeError("Failed to generate after maximum retries")


class PPLInferenceTask:
    """
    Compute PPL & IFD by streaming JSONL → HTTP → JSONL, one record at a time.
    """

    def __init__(self, input_file: str, output_dir: str, num_records: int = 0, **kwargs: dict):
        self.input_file = input_file
        self.output_dir = output_dir
        self.model_cfg = kwargs["model_config"]
        self.max_len = kwargs.get("model_max_len", 17000)
        self.ckpt_interval = kwargs.get("checkpoint_interval", 100)
        self.doc_field = kwargs.get("doc_colname", "conversation_pretokenized")
        self.tgt_field = kwargs.get("target_doc_colname", "targets_pretokenized")

        self.validate_model_cfg(self.model_cfg)
        create_dir(self.output_dir)

    def validate_model_cfg(self, cfg: dict[str, Any]):
        """
        Validate the model configuration.
        """
        if "model_type" not in cfg:
            raise ValueError("Model type is required in the configuration.")
        elif "url" not in cfg or not cfg["url"]:
            raise ValueError("Model URL is required in the configuration.")
        elif cfg["model_type"] == "vllm" and "model_serving_name" not in cfg:
            raise ValueError("Model serving name is required for vLLM.")

    def execute(self) -> str:
        # load existing checkpoint IDs
        ckpt_path = os.path.join(self.output_dir, "ppl_ifd_latest_chkp.jsonl")
        if os.path.exists(ckpt_path):
            skip_ids = set(pd.read_json(ckpt_path, lines=True)["id"])
        else:
            skip_ids = set()

        out_path = os.path.join(self.output_dir, "ppl_ifd_output.jsonl")
        # start with an empty file
        open(out_path, "w").close()

        asyncio.run(self._run(skip_ids, out_path, ckpt_path))
        return out_path

    @staticmethod
    def get_logprob(prompt_logprob, key="logprob"):
        if isinstance(prompt_logprob, dict) and prompt_logprob:
            return next(iter(prompt_logprob.values())).get(key)
        return prompt_logprob  # For TGI, already has logprob value

    async def _run(self, skip_ids: set, out_path: str, ckpt_path: str):
        async with LogProbModel(self.model_cfg) as client:
            count_since_ckpt = 0

            with open(self.input_file) as inp, open(out_path, "a") as out_file:
                for line in tqdm(
                    inp,
                    desc="Processing IFD scores",
                    total=sum(1 for _ in open(self.input_file)),
                ):
                    rec = json.loads(line)
                    if rec.get("id") in skip_ids:
                        continue

                    length = rec.get("full_token_len", 0)
                    if length > self.max_len:
                        ifd = None
                    else:
                        try:
                            conv_lp = await client.generate(rec[self.doc_field])
                            tgt_lp = await client.generate(rec[self.tgt_field])

                            conv_logits = [
                                self.get_logprob(e)
                                for e in conv_lp
                                if e is not None and not math.isinf(self.get_logprob(e))
                            ]
                            tgt_logits = [
                                self.get_logprob(e)
                                for e in tgt_lp
                                if e is not None and not math.isinf(self.get_logprob(e))
                            ]

                            ppl = float(np.exp(-np.mean(conv_logits))) if conv_logits else None
                            ans_ppl = float(np.exp(-np.mean(tgt_logits))) if tgt_logits else None
                            ifd = (ppl / ans_ppl) if (ppl is not None and ans_ppl) else None
                        except Exception as e:
                            print(f"Error processing record: {e}")
                            ifd = None

                    metadata_ifd = {
                        "metadata": {
                            "quality_characteristics": {
                                "heuristic_based": {
                                    "ifd": {
                                        "ifd_model": self.model_cfg["model_serving_name"],
                                        "ifd_score": ifd,
                                    }
                                }
                            }
                        }
                    }
                    utils.deep_update(rec, metadata_ifd)

                    out_file.write(json.dumps(rec) + "\n")
                    count_since_ckpt += 1

                    if count_since_ckpt >= self.ckpt_interval:
                        out_file.flush()
                        os.replace(out_path, ckpt_path)
                        count_since_ckpt = 0


if __name__ == "__main__":
    task = PPLInferenceTask(
        input_file="/private/var/folders/b0/rzsw244n619b6_yq7_72jzhh0000gp/T/tmpr9zdb21x/ttr_tagging_output.jsonl",
        output_dir="/private/var/folders/b0/rzsw244n619b6_yq7_72jzhh0000gp/T/tmpr9zdb21x/",
        model_config={
            "model_type": "vllm",  # or "vllm"
            "url": "",
            "model_serving_name": "qwen-32B",  # only for vllm
            "timeout_seconds": 120,
            "max_retries": 3,
        },
        model_max_len=17000,
        doc_colname="conversation_pretokenized",
        target_doc_colname="targets_pretokenized",
    )
    task.execute()
