import uuid
from typing import List, Dict, Any
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.vector_stores.base import VectorStore

class QdrantStore(VectorStore):
    def __init__(self, workspace_directory: Path):
        self.collection_name = "migration_knowledge"
        # We will use local persistent storage in the workspace
        self.db_path = workspace_directory / "qdrant_db"
        self.client = QdrantClient(path=str(self.db_path))

    def build_index(self, chunks: List[str], metadata: List[Dict[str, Any]], model) -> None:
        if not chunks:
            return
            
        embeddings = model.encode(chunks, show_progress_bar=False)
        dimension = len(embeddings[0])

        # Recreate collection
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
            
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )

        points = []
        for i, (chunk, meta, emb) in enumerate(zip(chunks, metadata, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb.tolist(),
                    payload=meta
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def load_index(self, model) -> bool:
        if self.client.collection_exists(self.collection_name):
            return True
        return False

    def search(self, query: str, top_k: int, model) -> List[Dict[str, Any]]:
        if not self.client.collection_exists(self.collection_name):
            return []

        query_vector = model.encode([query], show_progress_bar=False)[0].tolist()

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )

        results = []
        for hit in search_result:
            results.append({
                "score": hit.score,
                "source": hit.payload.get("source", ""),
                "content": hit.payload.get("content", "")
            })
        return results
