from datetime import datetime, timedelta, timezone
from telethon.tl.types import Channel, Chat, User
from utils.logger import setup_logger

logger = setup_logger("GroupService")

class GroupService:
    def __init__(self, client, ws_manager):
        self.client = client
        self.ws_manager = ws_manager
        self.home_group_id = None
        self.source_group_ids = []
        self.blacklist = set()
        
        # Cache
        self.groups_cache = []
        self.home_members_cache = set()

    async def fetch_groups(self):
        """Mengambil daftar semua grup yang diikuti userbot"""
        logger.info("Fetching dialogs...")
        dialogs = await self.client.get_dialogs()
        self.groups_cache = []
        
        for dialog in dialogs:
            if isinstance(dialog.entity, (Channel, Chat)):
                self.groups_cache.append({
                    "id": dialog.entity.id,
                    "title": dialog.title,
                    "type": "megagroup" if getattr(dialog.entity, "megagroup", False) else "normal",
                    "participants_count": getattr(dialog.entity, "participants_count", 0)
                })
                
        await self.ws_manager.broadcast({
            "type": "groups", "event": "fetched", "count": len(self.groups_cache)
        })
        return self.groups_cache

    def set_config(self, home_id: int, source_ids: list, blacklist: list):
        self.home_group_id = home_id
        self.source_group_ids = source_ids
        self.blacklist = set(blacklist)
        logger.info(f"Config updated: Home={home_id}, Sources={len(source_ids)}")

    async def get_home_members(self):
        """Mengambil ID member Home Group untuk validasi (mencegah invite ganda)"""
        if not self.home_group_id:
            return set()
            
        logger.info(f"Fetching members for Home Group {self.home_group_id}...")
        self.home_members_cache = set()
        
        async for user in self.client.iter_participants(self.home_group_id):
            if isinstance(user, User) and not user.bot and not user.deleted:
                self.home_members_cache.add(user.id)
                
        return self.home_members_cache

    async def get_active_members(self, days=30):
        """Menganalisis Source Group untuk mencari member aktif dalam N hari terakhir"""
        active_users = set()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        logger.info(f"Analyzing activity in {len(self.source_group_ids)} source groups since {cutoff_date}")
        
        for group_id in self.source_group_ids:
            logger.info(f"Scanning group {group_id}...")
            try:
                # iter_messages sangat efisien dan berhenti otomatis saat mencapai offset_date
                async for message in self.client.iter_messages(group_id, offset_date=cutoff_date):
                    if message.sender_id and isinstance(message.sender_id, int):
                        active_users.add(message.sender_id)
            except Exception as e:
                logger.error(f"Error scanning group {group_id}: {e}")
                
        logger.info(f"Found {len(active_users)} active users across source groups")
        return active_users