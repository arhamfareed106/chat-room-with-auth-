import json
from operator import concat
# from os import sync
from re import S
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Room, Message
from django.contrib.auth.models import User

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


    async def receive(self, text_data):         # type: ignore
        data = json.loads(text_data)
        message = data['message']
        username = data['username']
        room = data['room']

        await self.save_message(username, room, message) # type: ignore

        await self.channel_layer.group_send(           # type: ignore
            self.room_group_name,                               # type: ignore
             {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'room': room,
            } 
        )
    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        room = event['room']

        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'room': room, 
        }))


        @sync_to_async # type: ignore
        def save_message(username, room, message):
            user= User.objects.get(username=username)
            room= Room.objects.get(slug=room)

            Message.objects.create(user=user, room=room, content=message)