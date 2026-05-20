from django.contrib import admin
from .models import ChatRoom, Message, RoomMember

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['username', 'room', 'message_type', 'timestamp']
    list_filter = ['room', 'message_type', 'timestamp']
    search_fields = ['username', 'text']

@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'joined_at']