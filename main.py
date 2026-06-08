import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from utils.ws_manager import ConnectionManager
from utils.logger import setup_logger
from services.telegram_service import TelegramService
from services.group_service import GroupService
from services.sync_service import SyncService
from routes.auth import router as auth_router
from routes.groups import router as groups_router
from routes.sync import router as sync_router

settings = get_settings()

# Inisialisasi instance di level module agar bisa diakses oleh WebSocket endpoint
ws_manager = ConnectionManager()
telegram_service = TelegramService(ws_manager)

# Lifespan Context Manager untuk Startup & Shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    logger = setup_logger("Main", ws_manager)
    logger.info(f"[{settings.APP_NAME}] Initializing Telethon MTProto...")
    await telegram_service.start()
    
    group_service = None
    sync_service = None
    
    if telegram_service.client:
        group_service = GroupService(telegram_service.client, ws_manager)
        sync_service = SyncService(telegram_service.client, ws_manager, group_service)
        
        # Simpan ke app.state agar bisa diakses oleh Dependency Injection di routes
        app.state.group_service = group_service
        app.state.sync_service = sync_service
        logger.info("Group and Sync services initialized")
        
    # Simpan logger dan service lain ke app.state
    app.state.logger = logger
    app.state.ws_manager = ws_manager
    app.state.telegram_service = telegram_service
    
    yield  # <--- Aplikasi berjalan di sini (menangani request)
    
    # --- SHUTDOWN LOGIC ---
    logger.info(f"[{settings.APP_NAME}] Shutting down gracefully...")
    if sync_service and sync_service.is_syncing:
        await sync_service.stop_sync()
    await telegram_service.stop()

# Inisialisasi FastAPI dengan lifespan
app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

# CORS Middleware
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(auth_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(sync_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "telegram_connected": telegram_service.is_connected,
        "telegram_authorized": telegram_service.is_authorized
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Kirim status awal saat connect
        await ws_manager.send_personal_message({
            "type": "init",
            "telegram_connected": telegram_service.is_connected,
            "telegram_authorized": telegram_service.is_authorized
        }, websocket)

        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        # Menggunakan logger dari app.state
        if hasattr(app.state, 'logger'):
            app.state.logger.error(f"[WS] Fatal error: {e}")
        await ws_manager.disconnect(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        ws_ping_timeout=60,
        ws_ping_interval=20
    )