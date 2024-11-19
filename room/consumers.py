import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Room, Message

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

        # Add user to online users and notify others
        await self.add_user_to_online_list()
        await self.notify_user_joined()

    async def disconnect(self, close_code):
        # Remove user from online users and notify others
        await self.remove_user_from_online_list()
        await self.notify_user_left()

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(slug=self.room_name)
        message = Message.objects.create(
            room=room,
            user=self.user,
            content=content
        )
        return {
            'id': message.id,
            'content': message.content,
            'username': message.user.username,
            'timestamp': message.date_added.isoformat()
        }

    @database_sync_to_async
    def add_user_to_online_list(self):
        room = Room.objects.get(slug=self.room_name)
        if not hasattr(room, '_online_users'):
            room._online_users = set()
        room._online_users.add(self.user.username)
        return list(room._online_users)

    @database_sync_to_async
    def remove_user_from_online_list(self):
        room = Room.objects.get(slug=self.room_name)
        if hasattr(room, '_online_users'):
            room._online_users.discard(self.user.username)
            return list(room._online_users)
        return []

    async def notify_user_joined(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'username': self.user.username,
                'message': f'{self.user.username} joined the chat'
            }
        )

    async def notify_user_left(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_leave',
                'username': self.user.username,
                'message': f'{self.user.username} left the chat'
            }
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            message_content = data.get('message', '').strip()
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
                    'is_typing': data.get('is_typing', False)
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
        # Send typing status to WebSocket (only to other users)
        if event['username'] != self.user.username:
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'username': event['username'],
                'is_typing': event['is_typing']
            }))

    async def user_join(self, event):
        # Send user join notification
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'username': event['username'],
            'message': event['message']
        }))

    async def user_leave(self, event):
        # Send user leave notification
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'username': event['username'],
            'message': event['message']
        }))