import os
import time
import requests

class TokenExhaustedError(Exception):
    pass

class GitHubModelsClient:
    """GitHub Models (Azure-backed inference via GitHub token)."""
    def __init__(self):
        self.base_url = "https://models.inference.ai.azure.com"
        self.model_name = os.getenv("GITHUB_MODELS_MODEL_NAME", "gpt-4o-mini")

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = os.getenv("GITHUB_MODELS_TOKEN", "")
        if not key or key.startswith("your_"):
            raise ValueError("GitHub Models token not configured.")

        active_model = model_name or self.model_name
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        max_retries = 3
        delay = 10
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": active_model, "messages": messages, "temperature": 0.2},
                    timeout=60,
                )
                if resp.status_code == 429:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"GitHub Models rate limited after {max_retries} attempts.")
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code in (401, 403):
                    raise TokenExhaustedError(f"GitHub Models auth failed: {resp.status_code}")
                if resp.status_code >= 500:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"GitHub Models server error: {resp.status_code}")
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except TokenExhaustedError:
                raise
            except requests.exceptions.Timeout:
                if attempt == max_retries:
                    raise TokenExhaustedError("GitHub Models request timed out.")
                time.sleep(delay)
                delay *= 2
            except requests.exceptions.ConnectionError:
                raise TokenExhaustedError("GitHub Models connection error.")
        raise RuntimeError("Unexpected exit from retry loop")
