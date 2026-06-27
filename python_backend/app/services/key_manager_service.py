import json
import uuid
import base64
from pathlib import Path
from typing import List, Dict, Optional
from app.config import app_config

class KeyManagerService:
    def __init__(self):
        self.storage_file = app_config.workspace_directory / "api_keys.json"
        self._secret = b"ai_provider_secret_key_2026"
        self._ensure_storage()
        
    def _ensure_storage(self):
        if not self.storage_file.exists():
            default_data = {
                "active_provider": "groq",
                "providers": {
                    "groq": [],
                    "openai": [],
                    "gemini": []
                }
            }
            self.storage_file.write_text(json.dumps(default_data, indent=4))
            
    def _read_data(self) -> dict:
        try:
            return json.loads(self.storage_file.read_text())
        except Exception:
            return {"active_provider": "groq", "providers": {"groq": [], "openai": [], "gemini": []}}
            
    def _write_data(self, data: dict):
        self.storage_file.write_text(json.dumps(data, indent=4))
        
    def _encrypt(self, text: str) -> str:
        """Simple XOR obfuscation for local storage to prevent plaintext keys on disk."""
        if not text:
            return text
        text_bytes = text.encode('utf-8')
        encrypted = bytearray()
        for i in range(len(text_bytes)):
            encrypted.append(text_bytes[i] ^ self._secret[i % len(self._secret)])
        return base64.b64encode(encrypted).decode('utf-8')
        
    def _decrypt(self, text: str) -> str:
        if not text:
            return text
        try:
            encrypted_bytes = base64.b64decode(text.encode('utf-8'))
            decrypted = bytearray()
            for i in range(len(encrypted_bytes)):
                decrypted.append(encrypted_bytes[i] ^ self._secret[i % len(self._secret)])
            return decrypted.decode('utf-8')
        except Exception:
            return ""

    def _mask_key(self, key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        prefix = key[:4]
        suffix = key[-4:]
        return f"{prefix}_{'*' * 16}_{suffix}"

    # --- Provider Level ---
    
    def get_active_provider(self) -> str:
        data = self._read_data()
        return data.get("active_provider", "groq")
        
    def set_active_provider(self, provider_name: str):
        data = self._read_data()
        data["active_provider"] = provider_name
        self._write_data(data)

    # --- Key Level ---
    
    def get_keys(self, provider: str, unmask: bool = False) -> List[Dict]:
        data = self._read_data()
        keys = data.get("providers", {}).get(provider, [])
        result = []
        for k in keys:
            raw_key = self._decrypt(k.get("key", ""))
            k_copy = k.copy()
            if unmask:
                k_copy["key"] = raw_key
            else:
                k_copy["key"] = self._mask_key(raw_key)
            result.append(k_copy)
        
        # Sort so default is first
        result.sort(key=lambda x: not x.get("is_default", False))
        return result
        
    def get_active_keys(self, provider: str) -> List[Dict]:
        """Returns fully unmasked, active keys, default first."""
        all_keys = self.get_keys(provider, unmask=True)
        return [k for k in all_keys if k.get("is_active", True)]

    def add_key(self, provider: str, name: str, key_val: str, is_default: bool = False) -> Dict:
        data = self._read_data()
        if provider not in data["providers"]:
            data["providers"][provider] = []
            
        if is_default:
            for k in data["providers"][provider]:
                k["is_default"] = False
                
        new_key = {
            "id": str(uuid.uuid4()),
            "name": name,
            "key": self._encrypt(key_val),
            "is_active": True,
            "is_default": is_default or len(data["providers"][provider]) == 0
        }
        
        data["providers"][provider].append(new_key)
        self._write_data(data)
        
        ret = new_key.copy()
        ret["key"] = self._mask_key(key_val)
        return ret

    def edit_key(self, provider: str, key_id: str, name: str, key_val: Optional[str]) -> bool:
        data = self._read_data()
        keys = data.get("providers", {}).get(provider, [])
        for k in keys:
            if k["id"] == key_id:
                if name:
                    k["name"] = name
                if key_val:
                    k["key"] = self._encrypt(key_val)
                self._write_data(data)
                return True
        return False
        
    def delete_key(self, provider: str, key_id: str) -> bool:
        data = self._read_data()
        keys = data.get("providers", {}).get(provider, [])
        original_len = len(keys)
        data["providers"][provider] = [k for k in keys if k["id"] != key_id]
        
        if len(data["providers"][provider]) < original_len:
            # If we deleted the default, make the first one default if it exists
            deleted_default = not any(k.get("is_default") for k in data["providers"][provider])
            if deleted_default and data["providers"][provider]:
                data["providers"][provider][0]["is_default"] = True
            self._write_data(data)
            return True
        return False

    def toggle_key(self, provider: str, key_id: str, is_active: bool) -> bool:
        data = self._read_data()
        keys = data.get("providers", {}).get(provider, [])
        for k in keys:
            if k["id"] == key_id:
                k["is_active"] = is_active
                self._write_data(data)
                return True
        return False

    def set_default_key(self, provider: str, key_id: str) -> bool:
        data = self._read_data()
        keys = data.get("providers", {}).get(provider, [])
        found = False
        for k in keys:
            if k["id"] == key_id:
                k["is_default"] = True
                found = True
            else:
                k["is_default"] = False
        if found:
            self._write_data(data)
        return found

key_manager_service = KeyManagerService()
