# chat/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import ChatRoom, Message, RoomMember

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class ChatRoomSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'created_at', 'updated_at', 'message_count', 'member_count', 'last_message']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_member_count(self, obj):
        return obj.roommember_set.count()
    
    def get_last_message(self, obj):
        last_msg = obj.messages.first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None

# chat/serializers.py
class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'room', 'user', 'username', 'text', 'message_type', 
                  'file_url', 'file_name', 'file_size', 'timestamp', 'edited_at', 'reactions']
        read_only_fields = ['timestamp', 'edited_at']

class RoomMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = RoomMember
        fields = ['id', 'room', 'user', 'username', 'joined_at', 'last_active']
        read_only_fields = ['joined_at', 'last_active']
        