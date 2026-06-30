import os
from openai import OpenAI
from app.ai.base_provider import IAIProvider

class OpenAIClient(IAIProvider):
    def __init__(self):
        self.model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo")
    
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        return self.generate_with_metadata(prompt, system_instruction, api_key, model_name)["content"]

    def generate_with_metadata(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> dict:
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
        
        response = client.chat.completions.create(
            model=active_model,
            messages=messages,
            temperature=0.2
        )
        return {
            "content": response.choices[0].message.content,
            "usage": getattr(response, "usage", None),
            "model": active_model,
        }
