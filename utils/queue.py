import asyncio
import random
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerIdInvalidError
from telethon.tl.functions.channels import InviteToChannelRequest
from utils.logger import setup_logger

logger = setup_logger("InviteQueue")

class InviteQueue:
    def __init__(self, client, ws_manager):
        self.client = client
        self.ws_manager = ws_manager
        self.queue = asyncio.Queue()
        self.is_running = False
        self.worker_task = None
        
        # Statistik
        self.stats = {"success": 0, "failed": 0, "skipped": 0, "floodwait": 0}
        
        # Konfigurasi Delay (bisa diubah via API/WS nanti)
        self.delay_min = 30
        self.delay_max = 60

    async def start(self):
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("Invite Queue started")

    async def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
        logger.info("Invite Queue stopped")

    async def add(self, user_id: int, group_id: int):
        await self.queue.put({"user_id": user_id, "group_id": group_id})

    async def _worker(self):
        while self.is_running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue get error: {e}")
                continue

            user_id = task["user_id"]
            group_id = task["group_id"]
            
            try:
                await self.client(InviteToChannelRequest(
                    channel=group_id,
                    users=[user_id]
                ))
                self.stats["success"] += 1
                await self.ws_manager.broadcast({
                    "type": "sync", "event": "invite_success", "user_id": user_id
                })
                
                # Delay dinamis acak untuk menghindari pola deteksi bot
                delay = random.uniform(self.delay_min, self.delay_max)
                await asyncio.sleep(delay)
                
            except FloodWaitError as e:
                self.stats["floodwait"] += 1
                wait_time = e.seconds + 15 # Tambah buffer 15 detik
                logger.warning(f"FloodWait encountered. Sleeping for {wait_time}s")
                await self.ws_manager.broadcast({
                    "type": "sync", "event": "floodwait", "seconds": wait_time
                })
                await asyncio.sleep(wait_time)
                # Masukkan kembali ke antrian untuk di-retry
                await self.queue.put(task)
                
            except (UserPrivacyRestrictedError, PeerIdInvalidError):
                self.stats["skipped"] += 1
                logger.info(f"User {user_id} restricted or invalid")
                
            except Exception as e:
                self.stats["failed"] += 1
                logger.error(f"Failed to invite {user_id}: {e}")
                
            finally:
                self.queue.task_done()