import asyncio
from utils.logger import setup_logger
from utils.queue import InviteQueue
from services.group_service import GroupService

logger = setup_logger("SyncService")

class SyncService:
    def __init__(self, client, ws_manager, group_service: GroupService):
        self.client = client
        self.ws_manager = ws_manager
        self.group_service = group_service
        self.invite_queue = InviteQueue(client, ws_manager)
        self.is_syncing = False
        self.sync_task = None

    async def start_sync(self, days=30):
        if self.is_syncing:
            logger.warning("Sync already in progress")
            return False
            
        self.is_syncing = True
        self.sync_task = asyncio.create_task(self._run_sync(days))
        return True

    async def stop_sync(self):
        self.is_syncing = False
        await self.invite_queue.stop()
        if self.sync_task:
            self.sync_task.cancel()
        logger.info("Sync stopped by user")
        await self.ws_manager.broadcast({"type": "sync", "event": "stopped"})

    async def _run_sync(self, days):
        try:
            await self.ws_manager.broadcast({"type": "sync", "event": "started"})
            await self.invite_queue.start()
            
            # 1. Ambil member Home Group saat ini
            home_members = await self.group_service.get_home_members()
            
            # 2. Analisis dan ambil member aktif dari Source Groups
            active_members = await self.group_service.get_active_members(days)
            
            # 3. Validasi dan masukkan ke Queue
            queued_count = 0
            for user_id in active_members:
                if not self.is_syncing:
                    break
                    
                # VALIDASI KRITERIA
                if user_id in home_members:
                    continue # Sudah di Home Group
                if user_id in self.group_service.blacklist:
                    continue # Masuk Blacklist
                    
                # Lolos validasi, masukkan ke antrian invite
                await self.invite_queue.add(user_id, self.group_service.home_group_id)
                queued_count += 1
                
            logger.info(f"Queued {queued_count} valid members for invitation")
            await self.ws_manager.broadcast({
                "type": "sync", "event": "queued", "count": queued_count
            })
            
            # Tunggu antrian selesai atau ada sinyal stop
            while self.is_syncing and not self.invite_queue.queue.empty():
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Sync task cancelled")
        except Exception as e:
            logger.error(f"Sync error: {e}")
        finally:
            self.is_syncing = False
            await self.invite_queue.stop()
            await self.ws_manager.broadcast({"type": "sync", "event": "completed"})

    def get_stats(self):
        return {
            "is_syncing": self.is_syncing,
            "queue_size": self.invite_queue.queue.qsize(),
            "stats": self.invite_queue.stats
        }