import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from .models import Room, Message
from django.contrib.auth.models import User

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

        # Add user to room participants
        if self.user.is_authenticated:
            await self.add_participant()

        # Accept the WebSocket connection
        await self.accept()

        # Notify others that user has joined
        if self.user.is_authenticated:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_join',
                    'username': self.user.username,
                    'participant_count': await self.get_participant_count()
                }
            )

    async def disconnect(self, close_code):
        # Remove user from room participants
        if self.user.is_authenticated:
            await self.remove_participant()
            
            # Notify others that user has left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_leave',
                    'username': self.user.username,
                    'participant_count': await self.get_participant_count()
                }
            )

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            message = data['message']
            username = self.user.username

            # Save message to database
            room = await self.get_room()
            if room:
                await self.save_message(username, room, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'timestamp': timezone.now().isoformat()
                }
            )
        elif message_type == 'typing':
            # Broadcast typing status
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'username': self.user.username,
                    'is_typing': data['is_typing']
                }
            )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'timestamp': event['timestamp']
        }))

    async def typing_status(self, event):
        # Send typing status to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'username': event['username'],
            'is_typing': event['is_typing']
        }))

    async def user_join(self, event):
        # Send user join notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'username': event['username'],
            'participant_count': event['participant_count']
        }))

    async def user_leave(self, event):
        # Send user leave notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'username': event['username'],
            'participant_count': event['participant_count']
        }))

    @sync_to_async
    def get_room(self):
        try:
            return Room.objects.get(slug=self.room_name)
        except Room.DoesNotExist:
            return None

    @sync_to_async
    def save_message(self, username, room, message):
        user = User.objects.get(username=username)
        Message.objects.create(user=user, room=room, content=message)

    @sync_to_async
    def add_participant(self):
        room = Room.objects.get(slug=self.room_name)
        room.participants.add(self.user)

    @sync_to_async
    def remove_participant(self):
        room = Room.objects.get(slug=self.room_name)
        room.participants.remove(self.user)

    @sync_to_async
    def get_participant_count(self):
        room = Room.objects.get(slug=self.room_name)
        return room.participants.count()