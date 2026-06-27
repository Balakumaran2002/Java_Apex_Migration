from abc import ABC, abstractmethod

class IAIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        """
        Generate a response from the AI provider.
        
        Args:
            prompt: The user prompt.
            system_instruction: The system prompt (optional).
            api_key: The API key to use for this request.
            model_name: The model to use (optional).
            
        Returns:
            The generated string response.
            
        Raises:
            Exception: If an error occurs, such as RateLimitError, which will be handled by ProviderManager.
        """
        pass
