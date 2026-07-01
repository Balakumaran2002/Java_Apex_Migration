from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import api
from app.routers import api_keys

app = FastAPI(title="Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router, prefix="/api")
app.include_router(api_keys.router)
from app.routers import enterprise_api
from app.routers import scheduler_api
app.include_router(enterprise_api.router, prefix="/api")
app.include_router(scheduler_api.scheduler_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
