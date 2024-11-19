import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope['user']

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def save_message(self, message_content):
        room = Room.objects.get(slug=self.room_name)
        message = Message.objects.create(
            room=room,
            user=self.user,
            content=message_content
        )
        return {
            'id': message.id,
            'content': message.content,
            'username': message.user.username,
            'timestamp': message.date_added.isoformat()
        }

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'message')
        
        if message_type == 'message':
            message_content = text_data_json.get('message', '')
            if message_content:
                # Save message to database
                message_data = await self.save_message(message_content)
                
                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data['content'],
                        'username': message_data['username'],
                        'message_id': message_data['id'],
                        'timestamp': message_data['timestamp']
                    }
                )
        elif message_type == 'typing':
            # Broadcast typing status
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'username': self.user.username,
                    'is_typing': text_data_json.get('is_typing', False)
                }
            )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        }))

    async def typing_status(self, event):
        # Send typing status to WebSocket
        if event['username'] != self.user.username:
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'username': event['username'],
                'is_typing': event['is_typing']
            }))