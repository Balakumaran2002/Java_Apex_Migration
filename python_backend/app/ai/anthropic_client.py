import os
import time

class TokenExhaustedError(Exception):
    pass

class AnthropicClient:
    def __init__(self):
        self.model_name = os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-haiku-20240307")

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key or key.startswith("your_"):
            raise ValueError("Anthropic API key not configured.")

        try:
            import anthropic
        except ImportError:
            raise TokenExhaustedError("anthropic package not installed. Run: pip install anthropic")

        client = anthropic.Anthropic(api_key=key)
        active_model = model_name or self.model_name

        max_retries = 3
        delay = 10
        for attempt in range(1, max_retries + 1):
            try:
                kwargs = {"model": active_model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
                if system_instruction:
                    kwargs["system"] = system_instruction

                resp = client.messages.create(**kwargs)
                return resp.content[0].text
            except anthropic.RateLimitError as e:
                if attempt == max_retries:
                    raise TokenExhaustedError(f"Anthropic rate limited after {max_retries} attempts: {e}")
                time.sleep(delay)
                delay *= 2
            except anthropic.AuthenticationError as e:
                raise TokenExhaustedError(f"Anthropic auth failed: {e}")
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"Anthropic server error: {e}")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise
        raise RuntimeError("Unexpected exit from retry loop")
