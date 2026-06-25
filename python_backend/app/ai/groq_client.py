import os
import time
from groq import Groq
from groq import RateLimitError

class TokenExhaustedError(Exception):
    pass

class GroqClient:
    def __init__(self):
        self.model_name = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
        
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key or key == "your_groq_api_key_here":
            raise ValueError("Groq API key is not configured. Please configure it in .env")
            
        client = Groq(api_key=key)
        active_model = model_name or self.model_name
        if active_model == "llama3-70b-8192" or "gemini" in active_model.lower() or "gpt" in active_model.lower():
            active_model = "llama-3.3-70b-versatile"
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            
        messages.append({"role": "user", "content": prompt})
        
        max_retries = 3
        delay = 20
        
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    messages=messages,
                    model=active_model,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                if attempt == max_retries:
                    raise TokenExhaustedError(f"Groq limits exhausted after {max_retries} attempts: {str(e)}")
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                raise e
        
        raise RuntimeError("Unexpected exit from retry loop")
