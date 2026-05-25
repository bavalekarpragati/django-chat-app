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
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"Call WebSocket disconnected from {self.room_name}")
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Broadcast to all clients in the room except sender
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_signal',
                'data': data,
                'sender_channel': self.channel_name
            }
        )
    
    async def call_signal(self, event):
        # Send to WebSocket
        await self.send(text_data=json.dumps(event['data']))