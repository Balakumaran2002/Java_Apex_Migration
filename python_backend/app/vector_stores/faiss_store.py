import json
import faiss
import numpy as np
from typing import List, Dict, Any
from pathlib import Path

from app.vector_stores.base import VectorStore

class FAISSStore(VectorStore):
    def __init__(self, workspace_directory: Path):
        self.index_path = workspace_directory / "faiss_index.bin"
        self.meta_path = workspace_directory / "metadata.json"
        self.index = None
        self.metadata = []

    def build_index(self, chunks: List[str], metadata: List[Dict[str, Any]], model) -> None:
        if not chunks:
            return
            
        embeddings = model.encode(chunks, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
            
        self.metadata = metadata

    def load_index(self, model) -> bool:
        if self.index_path.exists() and self.meta_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            return True
        return False

    def search(self, query: str, top_k: int, model) -> List[Dict[str, Any]]:
        if self.index is None:
            return []
            
        query_vector = model.encode([query], show_progress_bar=False)
        query_vector = np.array(query_vector).astype('float32')
        
        distances, indices = self.index.search(query_vector, min(top_k, len(self.metadata)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata) and idx >= 0:
                results.append({
                    "score": float(distances[0][i]),
                    "source": self.metadata[idx]["source"],
                    "content": self.metadata[idx]["content"]
                })
        return results
