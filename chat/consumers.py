# chat/consumers.py - Enhanced version for your models
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, Message, RoomMember
from django.contrib.auth.models import User
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        # Get or create chat room
        self.room = await self.get_or_create_room()
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # If user is authenticated, add to room members
        if self.scope['user'].is_authenticated:
            await self.add_room_member()
        
        # Send recent messages (last 50)
        await self.send_recent_messages()
        
        # Announce user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'system_message',
                'message': f"{self.get_username()} joined the chat",
                'message_type': 'system'
            }
        )
    
    async def disconnect(self, close_code):
        # Announce user left
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'system_message',
                    'message': f"{self.get_username()} left the chat",
                    'message_type': 'system'
                }
            )
            
            # Remove from room members if authenticated
            if self.scope['user'].is_authenticated:
                await self.remove_room_member()
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'text')
        
        if message_type == 'message':
            await self.handle_text_message(text_data_json)
        elif message_type == 'typing':
            await self.handle_typing(text_data_json)
        elif message_type == 'image':
            await self.handle_image_message(text_data_json)
        elif message_type == 'file':
            await self.handle_file_message(text_data_json)
    
    async def handle_text_message(self, data):
        message_text = data.get('message', '')
        username = data.get('username', self.get_username())
        
        # Save message to database
        saved_message = await self.save_message(
            text=message_text,
            message_type='text',
            username=username
        )
        
        # Send to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': saved_message['id'],
                'message': message_text,
                'username': username,
                'timestamp': saved_message['timestamp'],
                'message_type': 'text'
            }
        )
    
    async def handle_image_message(self, data):
        # For images (you'll implement file upload later)
        image_url = data.get('image_url', '')
        username = data.get('username', self.get_username())
        
        saved_message = await self.save_message(
            text='[Image]',
            message_type='image',
            file_url=image_url,
            username=username
        )
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': saved_message['id'],
                'message': '[Image]',
                'username': username,
                'timestamp': saved_message['timestamp'],
                'message_type': 'image',
                'file_url': image_url
            }
        )
    
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', True)
        username = data.get('username', self.get_username())
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_typing',
                'username': username,
                'is_typing': is_typing
            }
        )
    
    async def handle_file_message(self, data):
        # For file sharing
        file_url = data.get('file_url', '')
        filename = data.get('filename', 'file')
        username = data.get('username', self.get_username())
        
        saved_message = await self.save_message(
            text=f'[File: {filename}]',
            message_type='file',
            file_url=file_url,
            username=username
        )
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': saved_message['id'],
                'message': f'📎 {filename}',
                'username': username,
                'timestamp': saved_message['timestamp'],
                'message_type': 'file',
                'file_url': file_url
            }
        )
    
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message_id': event.get('message_id'),
            'message': event['message'],
            'username': event['username'],
            'timestamp': event['timestamp'],
            'message_type': event.get('message_type', 'text'),
            'file_url': event.get('file_url', '')
        }))
    
    async def system_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': event['message'],
            'message_type': 'system'
        }))
    
    async def user_typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'username': event['username'],
            'is_typing': event['is_typing']
        }))
    
    async def send_recent_messages(self):
        messages = await self.get_recent_messages()
        for message in messages:
            await self.send(text_data=json.dumps({
                'type': 'message',
                'message_id': message['id'],
                'message': message['text'],
                'username': message['username'],
                'timestamp': message['timestamp'].isoformat() if message['timestamp'] else None,
                'message_type': message['message_type'],
                'file_url': message.get('file_url', ''),
                'is_historical': True
            }))
    
    # Database operations (all @database_sync_to_async)
    @database_sync_to_async
    def get_or_create_room(self):
        room, created = ChatRoom.objects.get_or_create(
            name=self.room_name
        )
        return room
    
    @database_sync_to_async
    def save_message(self, text, message_type, username, file_url=None):
        message = Message.objects.create(
            room=self.room,
            user=self.scope['user'] if self.scope['user'].is_authenticated else None,
            username=username,
            text=text,
            message_type=message_type,
            file_url=file_url
        )
        # Update room's updated_at
        self.room.updated_at = timezone.now()
        self.room.save()
        
        return {
            'id': message.id,
            'timestamp': message.timestamp.isoformat()
        }
    
    @database_sync_to_async
    def get_recent_messages(self):
        return list(Message.objects.filter(
            room=self.room
        ).order_by('-timestamp')[:50].values(
            'id', 'text', 'username', 'timestamp', 'message_type', 'file_url'
        ))
    
    @database_sync_to_async
    def add_room_member(self):
        RoomMember.objects.get_or_create(
            room=self.room,
            user=self.scope['user']
        )
    
    @database_sync_to_async
    def remove_room_member(self):
        RoomMember.objects.filter(
            room=self.room,
            user=self.scope['user']
        ).delete()
    
    def get_username(self):
        if self.scope['user'].is_authenticated:
            return self.scope['user'].username
        return "Anonymous"
    
    async def handle_edit(self, data):
        message_id = data.get('message_id')
        new_text = data.get('text')
        
        if self.scope['user'].is_authenticated:
            await self.edit_message(message_id, new_text)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'new_text': new_text,
                    'edited_at': str(timezone.now())
                }
            )

    async def handle_reaction(self, data):
        message_id = data.get('message_id')
        reaction = data.get('reaction')
        username = self.scope['user'].username
        
        await self.add_reaction(message_id, reaction, username)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_reaction',
                'message_id': message_id,
                'reaction': reaction,
                'username': username
            }
        )

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'edit',
            'message_id': event['message_id'],
            'new_text': event['new_text'],
            'edited_at': event['edited_at']
        }))

    async def message_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'message_id': event['message_id'],
            'reaction': event['reaction'],
            'username': event['username']
        }))