# chat/routing.py
from django.urls import re_path
from . import consumers
from . import call_consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>\w+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/call/(?P<room_name>\w+)/$', call_consumers.CallConsumer.as_asgi()),
]