import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwags']['room_name']
        self.romm_group_name = 'chat_%s' & self.room_name

        await self.channel_layer.group_add( # type: ignore
            self.room_group_name,           # type: ignore
            self.channel_name
        )


        await self.accept()

    async def disconnect(self,):            # type: ignore
         await self.channel_layer.group_discard(        # type: ignore
            self.room_group_name,                       # type: ignore
            self.channel_name
         )