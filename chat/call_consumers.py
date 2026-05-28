# chat/call_consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'call_{self.room_name}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"✅ Call WebSocket connected to {self.room_name}")
        
        # Notify that user is online for calls
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_signal',
                'data': {
                    'type': 'user_online',
                    'username': self.scope['user'].username if self.scope['user'].is_authenticated else 'Anonymous'
                }
            }
        )
    
    async def disconnect(self, close_code):
        # Notify that user left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_signal',
                'data': {
                    'type': 'user_offline',
                    'username': self.scope['user'].username if self.scope['user'].is_authenticated else 'Anonymous'
                }
            }
        )
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"Call WebSocket disconnected from {self.room_name}")
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        print(f"📞 Call signal received: {data.get('type')} from {data.get('from')} to {data.get('to')}")
        
        # Broadcast to ALL clients in the room (including sender)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_signal',
                'data': data
            }
        )
    
    async def call_signal(self, event):
        # Send to WebSocket
        data = event['data']
        print(f"📞 Broadcasting call signal: {data.get('type')}")
        await self.send(text_data=json.dumps(data))