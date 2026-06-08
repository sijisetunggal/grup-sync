import asyncio
import os
from typing import Optional
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneNumberBannedError
from config import get_settings
from utils.ws_manager import ConnectionManager

class TelegramService:
    def __init__(self, ws_manager: ConnectionManager):
        self.settings = get_settings()
        self.ws_manager = ws_manager
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        self.is_authorized = False
        self.session_string = os.getenv("SESSION_STRING", "")
        self._qr_task: Optional[asyncio.Task] = None
        self._qr_lock = asyncio.Lock()

    async def start(self):
        """Inisialisasi dan mulai koneksi MTProto ke Telegram"""
        session = StringSession(self.session_string) if self.session_string else StringSession()
        self.client = TelegramClient(
            session,
            self.settings.API_ID,
            self.settings.API_HASH,
            device_model="Userbot Migrasi",
            system_version="Web PWA",
            app_version="1.0.0",
            lang_code="id"
        )

        # Event handler untuk memantau update koneksi & pesan
        self.client.add_event_handler(self._on_update, events.Raw())

        try:
            await self.client.connect()
            self.is_connected = True
            await self.ws_manager.broadcast({
                "type": "status", "module": "telegram", "state": "connected"
            })

            self.is_authorized = await self.client.is_user_authorized()
            if not self.is_authorized:
                await self.ws_manager.broadcast({
                    "type": "auth", "state": "required", "method": "qr"
                })
            else:
                await self._save_session()
                await self.ws_manager.broadcast({
                    "type": "auth", "state": "authorized", 
                    "user": (await self.client.get_me()).username or "Unknown"
                })
        except PhoneNumberBannedError:
            await self.ws_manager.broadcast({"type": "auth", "state": "banned"})
        except Exception as e:
            self.is_connected = False
            await self.ws_manager.broadcast({
                "type": "status", "module": "telegram", "state": "error", "message": str(e)
            })
            print(f"[Telegram] Connection error: {e}")

    async def start_qr_login(self):
        """Memicu alur login QR Code via WebSocket"""
        if not self.client or not self.is_connected:
            await self.ws_manager.broadcast({"type": "error", "message": "Telegram client not connected"})
            return

        async with self._qr_lock:
            if self._qr_task and not self._qr_task.done():
                await self.ws_manager.broadcast({"type": "auth", "state": "qr_in_progress"})
                return
            self._qr_task = asyncio.create_task(self._qr_login_loop())

    async def _qr_login_loop(self):
        """Looping QR Code dengan refresh otomatis setiap 30 detik"""
        try:
            qr_login = await self.client.qr_login()
            while True:
                await self.ws_manager.broadcast({
                    "type": "auth", "state": "qr_show", "data": qr_login.data
                })
                try:
                    # Menunggu user scan (timeout default 30s)
                    await qr_login.wait(timeout=30)
                    break # Berhasil login
                except asyncio.TimeoutError:
                    await qr_login.recreate() # Refresh QR data
                except SessionPasswordNeededError:
                    await self.ws_manager.broadcast({"type": "auth", "state": "password_required"})
                    return
            
            self.is_authorized = True
            await self._save_session()
            me = await self.client.get_me()
            await self.ws_manager.broadcast({
                "type": "auth", "state": "authorized", "user": me.username or str(me.id)
            })
            print("[Telegram] QR Login successful!")
        except Exception as e:
            await self.ws_manager.broadcast({"type": "auth", "state": "failed", "message": str(e)})
        finally:
            self._qr_task = None

    async def submit_2fa_password(self, password: str):
        """Handle 2FA jika akun memilikinya"""
        if not self.client:
            return False
        try:
            await self.client.sign_in(password=password)
            self.is_authorized = True
            await self._save_session()
            await self.ws_manager.broadcast({"type": "auth", "state": "authorized"})
            return True
        except Exception as e:
            await self.ws_manager.broadcast({"type": "auth", "state": "2fa_failed", "message": str(e)})
            return False

    async def _save_session(self):
        """Simpan session string ke environment/log untuk persistensi"""
        if self.client:
            new_session = self.client.session.save()
            if new_session != self.session_string:
                self.session_string = new_session
                print("[Security] New SESSION_STRING generated. Update your HF Spaces Secret!")
                # Di production, bisa dikirim ke frontend untuk disimpan di PouchDB 
                # atau disimpan ke database terenkripsi.

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            self.is_connected = False
            self.is_authorized = False
            await self.ws_manager.broadcast({
                "type": "status", "module": "telegram", "state": "disconnected"
            })

    async def _on_update(self, event):
        """Handler untuk semua update dari Telegram (bisa dikembangkan untuk sync realtime)"""
        pass