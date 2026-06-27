# ai_factory.py
# =============
# Thin shim that keeps the existing AIFactory.get_client() public API
# while delegating all work to the new ProviderManager.
#
# NOTHING else in the codebase needs to change.
# All existing .generate(prompt, system_instruction, api_key, model_name) calls
# continue to work exactly as before.

from app.ai.provider_manager import get_provider_manager


class AIFactory:
    @staticmethod
    def get_client(provider_name: str = None):
        """
        Returns the ProviderManager singleton.

        The ProviderManager exposes the same .generate() interface as the
        old FallbackClient, so all existing callers work without modification.

        provider_name is accepted for backward compatibility but ignored —
        the ProviderManager handles provider selection automatically, using
        the configured AI_PROVIDER as the preferred first choice.
        """
        return get_provider_manager()
