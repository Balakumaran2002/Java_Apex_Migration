import os
from pathlib import Path
from typing import List, Dict

class ChunkingService:
    MAX_FILES = 100
    MAX_SIZE_KB = 500

    def chunk_repository(self, project_dir: Path) -> Dict[str, dict]:
        """
        Recursively groups files into modular chunks to avoid overloading the LLM.
        Returns a dict of ChunkState dicts.
        """
        chunks = {}
        chunk_counter = 1
        
        current_chunk_files = []
        current_chunk_size = 0
        
        # We perform a basic directory walk to chunk by Folder/Package
        for root, dirs, files in os.walk(project_dir):
            # Skip hidden and generated dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ["target", "build", "node_modules"]]
            
            for f in files:
                if f.startswith('.'): continue
                
                filepath = Path(root) / f
                
                # Filter extensions
                if not filepath.suffix in ['.java', '.xml', '.properties', '.yml', '.yaml', '.gradle', '.kts', '.js', '.jsx', '.ts', '.tsx', '.jsp']:
                    continue
                    
                try:
                    size_kb = filepath.stat().st_size / 1024.0
                except OSError:
                    continue
                    
                # If adding this file exceeds limits, seal the current chunk
                if len(current_chunk_files) >= self.MAX_FILES or (current_chunk_size + size_kb) > self.MAX_SIZE_KB:
                    if current_chunk_files:
                        chunk_id = f"chunk_{chunk_counter}"
                        chunks[chunk_id] = {
                            "chunk_id": chunk_id,
                            "files": current_chunk_files,
                            "status": "PENDING",
                            "error_message": "",
                            "retries": 0
                        }
                        chunk_counter += 1
                        current_chunk_files = []
                        current_chunk_size = 0
                
                current_chunk_files.append(str(filepath))
                current_chunk_size += size_kb
                
        # Add remainder
        if current_chunk_files:
            chunk_id = f"chunk_{chunk_counter}"
            chunks[chunk_id] = {
                "chunk_id": chunk_id,
                "files": current_chunk_files,
                "status": "PENDING",
                "error_message": "",
                "retries": 0
            }
            
        return chunks

chunking_service = ChunkingService()
