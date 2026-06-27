from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from app.services.key_manager_service import key_manager_service

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

SUPPORTED_PROVIDERS = {"groq", "openai", "gemini"}

def _validate_provider(provider: str):
    if provider.lower() not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider {provider} is not supported.")
    return provider.lower()

@router.get("/active-provider")
def get_active_provider():
    return {"active_provider": key_manager_service.get_active_provider()}

@router.put("/active-provider")
def set_active_provider(provider: str = Body(..., embed=True)):
    provider = _validate_provider(provider)
    key_manager_service.set_active_provider(provider)
    return {"message": "Active provider updated", "active_provider": provider}

@router.get("/{provider}")
def get_keys(provider: str):
    provider = _validate_provider(provider)
    # Return masked keys for security
    keys = key_manager_service.get_keys(provider, unmask=False)
    return {"provider": provider, "keys": keys}

@router.post("/{provider}")
def add_key(
    provider: str,
    name: str = Body(...),
    key_val: str = Body(..., alias="key"),
    is_default: bool = Body(False)
):
    provider = _validate_provider(provider)
    if not key_val.strip():
        raise HTTPException(status_code=400, detail="Key value cannot be empty.")
    new_key = key_manager_service.add_key(provider, name, key_val, is_default)
    return {"message": "Key added successfully", "key": new_key}

@router.put("/{provider}/{key_id}")
def edit_key(
    provider: str,
    key_id: str,
    name: Optional[str] = Body(None),
    key_val: Optional[str] = Body(None, alias="key")
):
    provider = _validate_provider(provider)
    success = key_manager_service.edit_key(provider, key_id, name, key_val)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Key updated successfully"}

@router.delete("/{provider}/{key_id}")
def delete_key(provider: str, key_id: str):
    provider = _validate_provider(provider)
    success = key_manager_service.delete_key(provider, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Key deleted successfully"}

@router.patch("/{provider}/{key_id}/status")
def toggle_key(
    provider: str,
    key_id: str,
    is_active: bool = Body(..., embed=True)
):
    provider = _validate_provider(provider)
    success = key_manager_service.toggle_key(provider, key_id, is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Key status updated successfully"}

@router.patch("/{provider}/{key_id}/default")
def set_default_key(provider: str, key_id: str):
    provider = _validate_provider(provider)
    success = key_manager_service.set_default_key(provider, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": "Default key updated successfully"}
