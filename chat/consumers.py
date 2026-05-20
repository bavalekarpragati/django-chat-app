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
        action = text_data_json.get('action', text_data_json.get('type', 'message'))
        
        if action == 'message' or action == 'text':
            await self.handle_text_message(text_data_json)
        elif action == 'edit':
            await self.handle_edit_message(text_data_json)
        elif action == 'delete':
            await self.handle_delete_message(text_data_json)
        elif action == 'typing':
            await self.handle_typing(text_data_json)
        elif action in ['image', 'video', 'audio', 'file']:
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
    
    # async def handle_file_message(self, data):
    #     # For file sharing
    #     file_url = data.get('file_url', '')
    #     filename = data.get('filename', 'file')
    #     username = data.get('username', self.get_username())
        
    #     saved_message = await self.save_message(
    #         text=f'[File: {filename}]',
    #         message_type='file',
    #         file_url=file_url,
    #         username=username
    #     )
        
    #     await self.channel_layer.group_send(
    #         self.room_group_name,
    #         {
    #             'type': 'chat_message',
    #             'message_id': saved_message['id'],
    #             'message': f'📎 {filename}',
    #             'username': username,
    #             'timestamp': saved_message['timestamp'],
    #             'message_type': 'file',
    #             'file_url': file_url
    #         }
    #     )
    # Add this method to handle file messages
    async def handle_file_message(self, data):
        """Handle file sharing in chat"""
        file_url = data.get('file_url', '')
        file_name = data.get('file_name', 'file')
        file_type = data.get('file_type', 'file')
        file_size = data.get('file_size', 0)
        username = data.get('username', self.get_username())
        
        if not file_url:
            return
        
        # Create display message based on file type
        icons = {
            'image': '📸',
            'video': '🎥', 
            'audio': '🎵',
            'document': '📄',
            'file': '📎'
        }
        
        icon = icons.get(file_type, '📎')
        display_text = f'{icon} {file_name}'
        
        # Save message to database
        saved_message = await self.save_file_message(
            text=display_text,
            message_type=file_type,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            username=username
        )
        
        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'file_broadcast',
                'message_id': saved_message['id'],
                'message': display_text,
                'file_url': file_url,
                'file_name': file_name,
                'file_type': file_type,
                'file_size': file_size,
                'username': username,
                'timestamp': saved_message['timestamp']
            }
        )

    # Add this method to save file messages
    @database_sync_to_async
    def save_file_message(self, text, message_type, username, file_url=None, file_name=None, file_size=None):
        """Save file message to database"""
        message = Message.objects.create(
            room=self.room,
            user=self.scope['user'] if self.scope['user'].is_authenticated else None,
            username=username,
            text=text,
            message_type=message_type,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size or 0
        )
        
        # Update room's updated_at
        self.room.updated_at = timezone.now()
        self.room.save()
        
        return {
            'id': message.id,
            'timestamp': message.timestamp.isoformat()
        }

    # Add this method to broadcast file messages
    async def file_broadcast(self, event):
        """Send file message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'file',
            'message_id': event.get('message_id'),
            'message': event['message'],
            'file_url': event['file_url'],
            'file_name': event['file_name'],
            'file_type': event['file_type'],
            'file_size': event.get('file_size', 0),
            'username': event['username'],
            'timestamp': event['timestamp']
        }))

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

    async def handle_edit_message(self, data):
        """Handle message editing"""
        message_id = data.get('message_id')
        new_text = data.get('text', '')
        username = data.get('username', self.get_username())
        
        # Check if user can edit this message
        if await self.can_edit_message(message_id, username):
            await self.edit_message(message_id, new_text)
            
            # Broadcast edit to all users in room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'new_text': new_text,
                    'username': username,
                    'edited_at': str(timezone.now())
                }
            )

    async def handle_delete_message(self, data):
        """Handle message deletion (including files)"""
        message_id = data.get('message_id')
        username = data.get('username', self.get_username())
        
        # Check if user can delete this message
        if await self.can_delete_message(message_id, username):
            # Get message info before deletion
            message_info = await self.get_message_info(message_id)
            
            # Delete the physical file if it exists
            if message_info and message_info.get('file_url'):
                await self.delete_physical_file(message_info['file_url'])
            
            # Soft delete the message
            await self.soft_delete_message(message_id)
            
            # Broadcast deletion to all users in room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'username': username,
                    'is_file': message_info.get('file_url') is not None
                }
            )

    @database_sync_to_async
    def delete_physical_file(self, file_url):
        """Delete the actual file from storage"""
        import os
        from django.conf import settings
        
        if file_url:
            # Remove /media/ prefix to get relative path
            relative_path = file_url.replace(settings.MEDIA_URL, '')
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error deleting file: {e}")


    @database_sync_to_async
    def get_message_info(self, message_id):
        """Get message information including file details"""
        try:
            message = Message.objects.get(id=message_id)
            return {
                'file_url': message.file_url,
                'file_name': message.file_name,
                'is_file': bool(message.file_url)
            }
        except Message.DoesNotExist:
            return None

    async def message_edited(self, event):
        """Send edit notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'edit',
            'message_id': event['message_id'],
            'new_text': event['new_text'],
            'username': event['username'],
            'edited_at': event['edited_at']
        }))

    async def message_deleted(self, event):
        """Send delete notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'delete',
            'message_id': event['message_id'],
            'username': event['username'],
            'is_file': event.get('is_file', False)
        }))

    async def message_reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'message_id': event['message_id'],
            'reaction': event['reaction'],
            'username': event['username']
        }))

    @database_sync_to_async
    def can_edit_message(self, message_id, username):
        """Check if user can edit message"""
        try:
            message = Message.objects.get(id=message_id)
            # User can edit if they own the message or are staff
            return message.username == username or self.scope['user'].is_staff
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def can_delete_message(self, message_id, username):
        """Check if user can delete message"""
        try:
            message = Message.objects.get(id=message_id)
            # User can delete if they own the message or are staff
            return message.username == username or self.scope['user'].is_staff
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def edit_message(self, message_id, new_text):
        """Edit message in database"""
        try:
            message = Message.objects.get(id=message_id)
            message.edit_message(new_text)
        except Message.DoesNotExist:
            pass

    @database_sync_to_async
    def soft_delete_message(self, message_id):
        """Soft delete message"""
        try:
            message = Message.objects.get(id=message_id)
            message.soft_delete()
        except Message.DoesNotExist:
            pass