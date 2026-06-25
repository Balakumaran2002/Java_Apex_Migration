import os
from ollama import Client

class OllamaClient:
    def __init__(self):
        self.model_name = os.getenv("OLLAMA_MODEL_NAME", "llama3")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        client = Client(host=self.base_url)
        active_model = model_name or self.model_name
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat(
            model=active_model,
            messages=messages,
            options={"temperature": 0.2}
        )
        return response['message']['content']
