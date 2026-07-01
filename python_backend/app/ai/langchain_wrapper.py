from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import Field
from typing import Any, List, Optional
import time

from app.ai.api_key_manager import api_key_manager
from app.services.llm_runtime_service import llm_runtime_service

class CustomRotatingChatModel(BaseChatModel):
    model_name: str = Field(default="llama-3.3-70b-versatile")
    
    @property
    def _llm_type(self) -> str:
        return "custom_rotating"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        from langchain_core.runnables import RunnableBinding
        # To support bind_tools properly, we can just intercept kwargs.
        # But wait, BaseChatModel supports bind_tools by injecting 'tools' into kwargs.
        return super().bind_tools(tools, **kwargs)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import logging
        from langchain_openai import ChatOpenAI
        from langchain_groq import ChatGroq
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.ai.request_scheduler import request_scheduler
        
        logger = logging.getLogger("provider_manager")
        
        model_fallbacks = {
            "llama-3.3-70b-versatile": {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"},
            "default": {"groq": "llama-3.3-70b-versatile", "gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}
        }
        
        def get_fallback_model(orig_model, target_provider):
            if orig_model in model_fallbacks and target_provider in model_fallbacks[orig_model]:
                return model_fallbacks[orig_model][target_provider]
            return model_fallbacks["default"].get(target_provider, orig_model)

        # We will get the initial provider from api_key_manager just to know what we are targeting first
        try:
            from app.ai.api_key_manager import api_key_manager
            initial_provider, _ = api_key_manager.get_active_provider_and_key()
        except RuntimeError:
            initial_provider = "groq" # fallback string for scheduler queue

        current_model = get_fallback_model(self.model_name, initial_provider)

        def execute_llm(kid: str, kval: str) -> ChatResult:
            # Re-fetch provider inside the callback in case it rotated during queue wait
            from app.ai.api_key_manager import api_key_manager
            # Determine provider by inspecting the key (api_key_manager knows, but we can check the active one)
            active_provider, _ = api_key_manager.get_active_provider_and_key()
            active_model = get_fallback_model(self.model_name, active_provider)
            
            logger.info(f"[{active_provider.upper()}] Executing with key: {kid} using model: {active_model}")
            
            if active_provider == "openai":
                client = ChatOpenAI(model=active_model, api_key=kval, temperature=0.2)
            elif active_provider == "groq":
                client = ChatGroq(model=active_model, api_key=kval, temperature=0.2)
            elif active_provider == "gemini":
                client = ChatGoogleGenerativeAI(model=active_model, google_api_key=kval, temperature=0.2)
            else:
                raise ValueError(f"Unknown provider: {active_provider}")
            
            if "tools" in kwargs:
                client = client.bind_tools(kwargs["tools"])
                invoke_kwargs = {k: v for k, v in kwargs.items() if k != "tools"}
            else:
                invoke_kwargs = kwargs
            
            response = client.invoke(messages, stop=stop, config={"callbacks": [run_manager] if run_manager else []}, **invoke_kwargs)
            
            from langchain_core.outputs import ChatGeneration
            return ChatResult(generations=[ChatGeneration(message=response)])

        # Dispatch the request to the Enterprise Token Bucket Request Scheduler
        return request_scheduler.execute(initial_provider, current_model, execute_llm)

