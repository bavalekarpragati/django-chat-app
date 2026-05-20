from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ChatRoom(models.Model):
    """Chat room model"""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-updated_at']

class Message(models.Model):
    """Message model"""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File'),
        ('system', 'System Message'),
    ]
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    username = models.CharField(max_length=150)
    text = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    file_url = models.CharField(max_length=500, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
     # Add these new fields to existing model
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    reactions = models.JSONField(default=dict)  # Store reactions like {"👍": ["user1", "user2"]}
    file = models.FileField(upload_to='chat_files/%Y/%m/%d/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.IntegerField(default=0)  # Size in bytes
    file_type = models.CharField(max_length=100, blank=True, null=True)  # MIME type
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    
    def __str__(self):
        return f"{self.username}: {self.text[:50]}"
    
    def edit_message(self, new_text):
        """Edit message content"""
        self.text = new_text
        self.edited_at = timezone.now()
        self.save()
    
    def soft_delete(self):
        """Soft delete message (mark as deleted)"""
        self.is_deleted = True
        self.text = "🚫 This message was deleted"
        self.save()
    
    def add_reaction(self, reaction, username):
        if reaction not in self.reactions:
            self.reactions[reaction] = []
        if username not in self.reactions[reaction]:
            self.reactions[reaction].append(username)
        self.save()
    
    class Meta:
        ordering = ['timestamp']

class RoomMember(models.Model):
    """Track users in rooms"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['room', 'user']
    
    def __str__(self):
        return f"{self.user.username} in {self.room.name}"