from abc import ABC, abstractmethod
from typing import List, Dict, Any

class VectorStore(ABC):
    @abstractmethod
    def build_index(self, chunks: List[str], metadata: List[Dict[str, Any]], model) -> None:
        pass

    @abstractmethod
    def load_index(self, model) -> bool:
        pass

    @abstractmethod
    def search(self, query: str, top_k: int, model) -> List[Dict[str, Any]]:
        pass
