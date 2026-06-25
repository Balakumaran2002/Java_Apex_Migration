import os
from google import genai
from google.genai import types

class TokenExhaustedError(Exception):
    pass

class GeminiClient:
    def __init__(self):
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Gemini API key is not configured. Please configure it in settings.")
        
        client = genai.Client(api_key=key)
        active_model = model_name or self.model_name
        if "llama" in active_model.lower() or "gpt" in active_model.lower():
            active_model = "gemini-2.5-flash"
        
        config_kwargs = {"temperature": 0.2}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
            
        config = types.GenerateContentConfig(**config_kwargs)
        
        from google.genai.errors import APIError
        import time
        
        max_retries = 4
        delay = 40
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=active_model,
                    contents=prompt,
                    config=config
                )
                return response.text
            except APIError as e:
                if e.code in (429, 503):
                    if attempt == max_retries:
                        raise TokenExhaustedError(f"Gemini tokens exhausted or service unavailable after {max_retries} attempts: {str(e)}")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise e
        raise RuntimeError("Unexpected exit from retry loop")
