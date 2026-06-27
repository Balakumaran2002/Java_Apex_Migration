import os
from groq import Groq
from app.ai.base_provider import IAIProvider

class GroqClient(IAIProvider):
    def __init__(self):
        self.model_name = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
        
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        # Default fallback to env for backward compatibility if no key passed
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key or key == "your_groq_api_key_here":
            raise ValueError("Groq API key is not configured.")
            
        client = Groq(api_key=key)
        active_model = model_name or self.model_name
        if active_model == "llama3-70b-8192" or "gemini" in active_model.lower() or "gpt" in active_model.lower():
            active_model = "llama-3.3-70b-versatile"
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            
        messages.append({"role": "user", "content": prompt})
        
        # Note: Internal retry loop for RateLimits is removed.
        # Rate limits are now caught by the ProviderManager which seamlessly rotates to the next API key.
        response = client.chat.completions.create(
            messages=messages,
            model=active_model,
            temperature=0.2
        )
        return response.choices[0].message.content
