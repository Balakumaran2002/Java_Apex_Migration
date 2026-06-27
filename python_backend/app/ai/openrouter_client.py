import os
import time
import requests

class TokenExhaustedError(Exception):
    pass

class OpenRouterClient:
    def __init__(self):
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = os.getenv("OPENROUTER_MODEL_NAME", "mistralai/mistral-7b-instruct")

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key or key.startswith("your_"):
            raise ValueError("OpenRouter API key not configured.")

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
                        raise TokenExhaustedError(f"OpenRouter rate limited after {max_retries} attempts.")
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code in (400, 401, 403):
                    raise TokenExhaustedError(f"OpenRouter auth or config failed ({resp.status_code}): {resp.text}")
                if resp.status_code >= 500:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"OpenRouter server error: {resp.status_code}")
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except TokenExhaustedError:
                raise
            except requests.exceptions.Timeout:
                if attempt == max_retries:
                    raise TokenExhaustedError("OpenRouter request timed out.")
                time.sleep(delay)
                delay *= 2
            except requests.exceptions.ConnectionError:
                raise TokenExhaustedError("OpenRouter connection error.")
        raise RuntimeError("Unexpected exit from retry loop")
