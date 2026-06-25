import os
import time
from openai import OpenAI
from openai import RateLimitError

class TokenExhaustedError(Exception):
    pass

class OpenAIClient:
    def __init__(self):
        self.model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo")
    
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key or key == "your_openai_api_key_here":
            raise ValueError("OpenAI API key is not configured.")
        
        client = OpenAI(api_key=key)
        active_model = model_name or self.model_name
        if "llama" in active_model.lower() or "gemini" in active_model.lower():
            active_model = "gpt-4o-mini"
            
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        max_retries = 3
        delay = 20
        
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                if attempt == max_retries:
                    raise TokenExhaustedError(f"OpenAI limits exhausted after {max_retries} attempts: {str(e)}")
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                raise e
        
        raise RuntimeError("Unexpected exit from retry loop")
