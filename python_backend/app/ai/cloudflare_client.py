import os
import time
import requests

class TokenExhaustedError(Exception):
    pass

class CloudflareClient:
    def __init__(self):
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        self.model_name = os.getenv("CLOUDFLARE_MODEL_NAME", "@cf/mistral/mistral-7b-instruct-v0.2-lora")

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = os.getenv("CLOUDFLARE_API_KEY", "")
        account_id = self.account_id
        if not key or key.startswith("your_") or not account_id:
            raise ValueError("Cloudflare Workers AI API key or account ID not configured.")

        active_model = model_name or self.model_name
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{active_model}"

        max_retries = 3
        delay = 10
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"messages": messages},
                    timeout=60,
                )
                if resp.status_code == 429:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"Cloudflare AI rate limited after {max_retries} attempts.")
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code in (401, 403):
                    raise TokenExhaustedError(f"Cloudflare AI auth failed: {resp.status_code}")
                if resp.status_code >= 500:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"Cloudflare AI server error: {resp.status_code}")
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data.get("result", {}).get("response", "")
            except TokenExhaustedError:
                raise
            except requests.exceptions.Timeout:
                if attempt == max_retries:
                    raise TokenExhaustedError("Cloudflare AI request timed out.")
                time.sleep(delay)
                delay *= 2
            except requests.exceptions.ConnectionError:
                raise TokenExhaustedError("Cloudflare AI connection error.")
        raise RuntimeError("Unexpected exit from retry loop")
