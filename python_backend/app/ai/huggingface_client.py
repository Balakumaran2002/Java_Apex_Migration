import os
import time
import requests

class TokenExhaustedError(Exception):
    pass

class HuggingFaceClient:
    def __init__(self):
        self.base_url = "https://api-inference.huggingface.co/models"
        self.model_name = os.getenv("HUGGINGFACE_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2")

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = os.getenv("HUGGINGFACE_API_KEY", "")
        if not key or key.startswith("your_"):
            raise ValueError("HuggingFace API key not configured.")

        active_model = model_name or self.model_name
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"

        max_retries = 3
        delay = 15
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/{active_model}",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"inputs": full_prompt, "parameters": {"temperature": 0.2, "max_new_tokens": 4096, "return_full_text": False}},
                    timeout=90,
                )
                if resp.status_code == 429:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"HuggingFace rate limited after {max_retries} attempts.")
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code in (401, 403):
                    raise TokenExhaustedError(f"HuggingFace auth failed: {resp.status_code}")
                if resp.status_code >= 500:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"HuggingFace server error: {resp.status_code}")
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                result = resp.json()
                if isinstance(result, list) and result:
                    return result[0].get("generated_text", "")
                return str(result)
            except TokenExhaustedError:
                raise
            except requests.exceptions.Timeout:
                if attempt == max_retries:
                    raise TokenExhaustedError("HuggingFace request timed out.")
                time.sleep(delay)
                delay *= 2
            except requests.exceptions.ConnectionError:
                raise TokenExhaustedError("HuggingFace connection error.")
        raise RuntimeError("Unexpected exit from retry loop")
