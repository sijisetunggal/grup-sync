from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from services.telegram_service import TelegramService

router = APIRouter(prefix="/auth", tags=["Authentication"])

class PasswordPayload(BaseModel):
    password: str

def get_telegram_service(request: Request) -> TelegramService:
    return request.app.state.telegram_service

@router.get("/status")
async def get_auth_status(tele: TelegramService = Depends(get_telegram_service)):
    """Cek status koneksi dan otorisasi Telegram"""
    return {
        "connected": tele.is_connected,
        "authorized": tele.is_authorized,
        "session_exists": bool(tele.session_string)
    }

@router.post("/qr/trigger")
async def trigger_qr_login(tele: TelegramService = Depends(get_telegram_service)):
    """Memulai proses QR Login (hasil dikirim via WebSocket)"""
    if not tele.is_connected:
        raise HTTPException(status_code=503, detail="Telegram client not connected")
    await tele.start_qr_login()
    return {"status": "qr_initiated", "message": "Check WebSocket for QR data"}

@router.post("/2fa/submit")
async def submit_2fa(payload: PasswordPayload, tele: TelegramService = Depends(get_telegram_service)):
    """Submit password 2FA jika diperlukan"""
    success = await tele.submit_2fa_password(payload.password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid 2FA password or session expired")
    return {"status": "success", "message": "2FA verified"}