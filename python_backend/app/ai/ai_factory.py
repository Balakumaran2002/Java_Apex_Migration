from app.ai.gemini_client import GeminiClient, TokenExhaustedError as GeminiExhaustedError
from app.ai.openai_client import OpenAIClient, TokenExhaustedError as OpenAIExhaustedError
from app.ai.groq_client import GroqClient, TokenExhaustedError as GroqExhaustedError
from app.ai.ollama_client import OllamaClient
from app.config import app_config

class FallbackClient:
    def __init__(self, initial_provider: str):
        self.initial_provider = initial_provider
        self.last_provider_used = initial_provider
        
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        # 1. Try initial provider
        self.last_provider_used = self.initial_provider
        if self.initial_provider == "openai":
            client = OpenAIClient()
        elif self.initial_provider == "ollama":
            client = OllamaClient()
        elif self.initial_provider == "groq":
            client = GroqClient()
        else:
            client = GeminiClient()
            
        try:
            return client.generate(prompt, system_instruction, api_key, model_name)
        except Exception as e:
            if type(e).__name__ == "TokenExhaustedError" or getattr(e, "code", None) == 429:
                print(f"Fallback triggered! {self.initial_provider} exhausted limits: {str(e)}")
                # Try Groq Fallback
                try:
                    print("Attempting Fallback to Groq...")
                    self.last_provider_used = "groq"
                    groq_client = GroqClient()
                    return groq_client.generate(prompt, system_instruction, None, None)
                except Exception as e2:
                    if type(e2).__name__ == "TokenExhaustedError" or getattr(e2, "code", None) == 429:
                        print(f"Groq Fallback failed due to limits: {str(e2)}")
                        # Try OpenAI Fallback
                        print("Attempting Fallback to OpenAI...")
                        self.last_provider_used = "openai"
                        openai_client = OpenAIClient()
                        return openai_client.generate(prompt, system_instruction, None, None)
                    raise e2
            raise e

class AIFactory:
    @staticmethod
    def get_client(provider_name: str = None):
        provider = provider_name or app_config.ai_provider
        provider = provider.lower()
        return FallbackClient(provider)

