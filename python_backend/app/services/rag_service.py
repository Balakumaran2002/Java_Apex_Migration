import os
import re
from sentence_transformers import SentenceTransformer
from app.config import app_config

class RagService:
    def __init__(self):
        self.is_initialized = False
        self.initialization_status = "Not Initialized"
        self.model = None
        
        self.knowledge_dir = app_config.project_root / "knowledge_base"
        
        if app_config.vector_db == "qdrant":
            from app.vector_stores.qdrant_store import QdrantStore
            self.store = QdrantStore(app_config.workspace_directory)
        else:
            from app.vector_stores.faiss_store import FAISSStore
            self.store = FAISSStore(app_config.workspace_directory)
            
        self.initialize_rag()
        
    def chunk_markdown(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        raw_sections = re.split(r'\n(##+ .*)\n', content)
        chunks = []
        current_header = ""
        
        for sec in raw_sections:
            sec = sec.strip()
            if not sec: continue
            
            if sec.startswith('##'):
                current_header = sec
            else:
                chunk_text = f"{current_header}\n{sec}" if current_header else sec
                if len(chunk_text) > 1200:
                    paragraphs = chunk_text.split('\n\n')
                    sub_chunk = ""
                    for p in paragraphs:
                        if len(sub_chunk) + len(p) < 1000:
                            sub_chunk += "\n\n" + p
                        else:
                            if sub_chunk.strip():
                                chunks.append(sub_chunk.strip())
                            sub_chunk = p
                    if sub_chunk.strip():
                        chunks.append(sub_chunk.strip())
                else:
                    chunks.append(chunk_text)
        return chunks

    def build_index(self):
        if not self.knowledge_dir.exists():
            self.initialization_status = f"Knowledge dir not found: {self.knowledge_dir}"
            return

        all_chunks = []
        metadata = []
        
        for filename in os.listdir(self.knowledge_dir):
            if filename.endswith('.md') or filename.endswith('.txt'):
                file_path = self.knowledge_dir / filename
                chunks = self.chunk_markdown(file_path)
                for c in chunks:
                    all_chunks.append(c)
                    metadata.append({
                        "source": filename,
                        "content": c
                    })
        
        if not all_chunks:
            self.initialization_status = "No documents found to index"
            return
            
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.store.build_index(all_chunks, metadata, self.model)
            self.is_initialized = True
            self.initialization_status = f"Successfully indexed {len(all_chunks)} chunks into {app_config.vector_db}."
        except Exception as e:
            self.model = None
            self.is_initialized = False
            self.initialization_status = f"RAG unavailable: {str(e)}"

    def load_index(self):
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            if self.store.load_index(self.model):
                self.is_initialized = True
                self.initialization_status = f"Successfully loaded index from {app_config.vector_db}."
            else:
                self.build_index()
        except Exception as e:
            self.initialization_status = f"Error loading index: {str(e)}"
            try:
                self.build_index()
            except Exception as build_error:
                self.model = None
                self.is_initialized = False
                self.initialization_status = f"RAG unavailable: {str(build_error)}"

    def initialize_rag(self):
        self.load_index()

    def search(self, query: str, top_k: int = 3):
        if not self.is_initialized:
            return []
            
        return self.store.search(query, top_k, self.model)

rag_service = RagService()
