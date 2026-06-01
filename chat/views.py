# chat/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.db.models import Q
from django.contrib.auth.models import User
from .models import ChatRoom, Message, RoomMember
from .serializers import ChatRoomSerializer, MessageSerializer, RoomMemberSerializer, UserSerializer
from django.db import models as django_models

# ============ TEMPLATE VIEWS (for web pages) ============

def index(request):
    """Home page - shows list of chat rooms"""
    rooms = ChatRoom.objects.all().order_by('-updated_at')
    return render(request, 'chat/index.html', {'rooms': rooms})

def room(request, room_name):
    """Individual chat room page"""
    # Get or create the room
    room, created = ChatRoom.objects.get_or_create(name=room_name)
    # Get recent messages
    messages = Message.objects.filter(room=room).order_by('-timestamp')[:50]
    
    # If user is authenticated, add them to room members
    if request.user.is_authenticated:
        RoomMember.objects.get_or_create(room=room, user=request.user)
    
    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'room': room,
        'messages': reversed(messages)  # Show oldest first
    })

# ============ REST API VIEWS ============

# Room APIs
class RoomListCreateView(generics.ListCreateAPIView):
    """List all rooms or create a new room"""
    queryset = ChatRoom.objects.all().order_by('-updated_at')
    serializer_class = ChatRoomSerializer
    #permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    # To this:
    permission_classes = [permissions.AllowAny]  # Allow anyone to create rooms
    
    def perform_create(self, serializer):
        try:
            room = serializer.save()
            # Only add member if user is authenticated
            if self.request.user and self.request.user.is_authenticated:
                RoomMember.objects.get_or_create(room=room, user=self.request.user)
        except Exception as e:
            # Log the error (you'll see it in terminal)
            print(f"Error creating room: {e}")
            raise

class RoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a specific room"""
    queryset = ChatRoom.objects.all()
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Message APIs
class RoomMessagesView(generics.ListAPIView):
    """Get all messages for a specific room"""
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return Message.objects.filter(room_id=room_id).order_by('-timestamp')[:100]

class MessageCreateView(generics.CreateAPIView):
    """Create a new message in a room"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        room_id = self.kwargs['room_id']
        room = get_object_or_404(ChatRoom, id=room_id)
        serializer.save(
            room=room, 
            user=self.request.user, 
            username=self.request.user.username
        )
        
        # Update room's updated_at timestamp
        room.save()  # This will update auto_now field

# Member APIs
class RoomMembersView(generics.ListAPIView):
    """Get all members of a room"""
    serializer_class = RoomMemberSerializer
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return RoomMember.objects.filter(room_id=room_id).select_related('user')

class JoinRoomView(APIView):
    """Join a chat room"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        member, created = RoomMember.objects.get_or_create(room=room, user=request.user)
        
        if created:
            # Create system message
            Message.objects.create(
                room=room,
                user=request.user,
                username='System',
                text=f"{request.user.username} joined the room",
                message_type='system'
            )
            return Response({
                'status': 'joined', 
                'message': f'Successfully joined {room.name}'
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'already_member', 
            'message': 'You are already a member of this room'
        }, status=status.HTTP_200_OK)

class LeaveRoomView(APIView):
    """Leave a chat room"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        deleted_count, _ = RoomMember.objects.filter(room=room, user=request.user).delete()
        
        if deleted_count > 0:
            # Create system message
            Message.objects.create(
                room=room,
                user=request.user,
                username='System',
                text=f"{request.user.username} left the room",
                message_type='system'
            )
            return Response({
                'status': 'left', 
                'message': f'Successfully left {room.name}'
            })
        return Response({
            'status': 'not_member', 
            'message': 'You are not a member of this room'
        }, status=status.HTTP_400_BAD_REQUEST)

# Search API
class SearchMessagesView(generics.ListAPIView):
    """Search messages in a room"""
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        query = self.request.query_params.get('q', '')
        
        if not query:
            return Message.objects.none()
        
        return Message.objects.filter(
            room_id=room_id,
            text__icontains=query
        ).order_by('-timestamp')[:50]

# User's active rooms
class UserRoomsView(generics.ListAPIView):
    """Get all rooms a user is a member of"""
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user_rooms = RoomMember.objects.filter(
            user=self.request.user
        ).values_list('room', flat=True)
        return ChatRoom.objects.filter(id__in=user_rooms).order_by('-updated_at')

# ============ FUNCTION-BASED API VIEWS (simpler alternatives) ============

@api_view(['GET'])
def get_room_by_name(request, room_name):
    """Get room details by name (useful for WebSocket rooms)"""
    try:
        room = ChatRoom.objects.get(name=room_name)
        serializer = ChatRoomSerializer(room)
        return Response(serializer.data)
    except ChatRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
def get_user_rooms_by_name(request, username):
    """Get all rooms for a specific user by username"""
    try:
        user = User.objects.get(username=username)
        user_rooms = RoomMember.objects.filter(user=user).values_list('room', flat=True)
        rooms = ChatRoom.objects.filter(id__in=user_rooms)
        serializer = ChatRoomSerializer(rooms, many=True)
        return Response(serializer.data)
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
def get_recent_messages(request, room_name):
    """Get recent messages for a room by name"""
    try:
        room = ChatRoom.objects.get(name=room_name)
        messages = Message.objects.filter(room=room).order_by('-timestamp')[:50]
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    except ChatRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_message_to_room(request, room_name):
    """Send a message to a room by name"""
    try:
        room = ChatRoom.objects.get(name=room_name)
        message_text = request.data.get('text', '')
        
        if not message_text:
            return Response(
                {'error': 'Message text is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message = Message.objects.create(
            room=room,
            user=request.user,
            username=request.user.username,
            text=message_text,
            message_type='text'
        )
        
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except ChatRoom.DoesNotExist:
        return Response(
            {'error': 'Room not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

# ============ STATS AND DASHBOARD VIEWS ============

@api_view(['GET'])
def get_chat_stats(request):
    """Get overall chat statistics"""
    stats = {
        'total_rooms': ChatRoom.objects.count(),
        'total_messages': Message.objects.count(),
        'total_users': User.objects.count(),
        'total_memberships': RoomMember.objects.count(),
        'rooms_with_most_messages': list(
            ChatRoom.objects.annotate(
                msg_count=django_models.Count('messages')
            ).order_by('-msg_count').values('name', 'msg_count')[:5]
        ),
        'most_active_users': list(
            Message.objects.values('username')
            .annotate(msg_count=django_models.Count('id'))
            .order_by('-msg_count')[:5]
        )
    }
    return Response(stats)

# Import models for stats
from django.db import models as django_models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# ============ SIMPLE HEALTH CHECK ============

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Simple health check endpoint"""
    return Response({
        'status': 'ok',
        'message': 'Chat API is running',
        'websocket': 'ws://localhost:8000/ws/chat/room-name/',
        'urls': {
            'home': '/',
            'room': '/room/<room_name>/',
            'api_rooms': '/api/rooms/',
            'api_health': '/api/health/'
        }
    })

# chat/views.py - Add this at the end of the file

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import ChatRoom, RoomMember, Message

from django.contrib.auth.models import User

class AddMemberToRoomView(APIView):
    """Add any registered user to a room"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        username = request.data.get('username')
        
        if not username:
            return Response(
                {'error': 'Username is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            user_to_add = User.objects.get(username=username)
            
            if RoomMember.objects.filter(room=room, user=user_to_add).exists():
                return Response(
                    {'error': f'{username} is already a member'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            RoomMember.objects.create(room=room, user=user_to_add)
            
            Message.objects.create(
                room=room,
                user=request.user,
                username='System',
                text=f"{username} was added to the room by {request.user.username}",
                message_type='system'
            )
            
            return Response({
                'success': True,
                'message': f'{username} added to room'
            }, status=status.HTTP_201_CREATED)
            
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
# chat/views.py - Add this class

class RemoveMemberFromRoomView(APIView):
    """Remove a user from a room"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        username = request.data.get('username')
        
        if not username:
            return Response(
                {'error': 'Username is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            room = ChatRoom.objects.get(id=room_id)
            user_to_remove = User.objects.get(username=username)
            
            # Check if user is in the room
            if not RoomMember.objects.filter(room=room, user=user_to_remove).exists():
                return Response(
                    {'error': f'{username} is not a member of this room'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Remove user from room
            RoomMember.objects.filter(room=room, user=user_to_remove).delete()
            
            # Create system message
            Message.objects.create(
                room=room,
                user=request.user,
                username='System',
                text=f"{username} was removed from the room by {request.user.username}",
                message_type='system'
            )
            
            return Response({
                'success': True,
                'message': f'{username} removed from room'
            }, status=status.HTTP_200_OK)
            
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        


# chat/views.py - Add this class

class ForwardMessageView(APIView):
    """Forward a message to another room"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id):
        try:
            original_message = Message.objects.get(id=message_id)
            target_room_id = request.data.get('room_id')
            target_room = ChatRoom.objects.get(id=target_room_id)
            
            # Create forwarded message
            forwarded_message = Message.objects.create(
                room=target_room,
                user=request.user,
                username=request.user.username,
                text=original_message.text,
                message_type=original_message.message_type,
                file_url=original_message.file_url,
                file_name=original_message.file_name,
                file_size=original_message.file_size,
                forwarded_from=original_message,
                is_forwarded=True,
                original_sender=original_message.username
            )
            
            # Create display text
            display_text = f"📎 Forwarded from {original_message.username}: {original_message.text[:100]}"
            
            return Response({
                'success': True,
                'message': 'Message forwarded',
                'forwarded_message': MessageSerializer(forwarded_message).data
            }, status=status.HTTP_201_CREATED)
            
        except Message.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)


# Add these imports at the top if not already present
from .models import PinnedMessage

class PinMessageView(APIView):
    """Pin or unpin a message in a room"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id):
        try:
            message = Message.objects.get(id=message_id)
            room = message.room
            
            # Check if already pinned
            pinned_exists = PinnedMessage.objects.filter(room=room, message=message).exists()
            
            if pinned_exists:
                # Unpin
                PinnedMessage.objects.filter(room=room, message=message).delete()
                return Response({
                    'success': True, 
                    'pinned': False,
                    'message': 'Message unpinned'
                }, status=status.HTTP_200_OK)
            else:
                # Pin
                PinnedMessage.objects.create(
                    room=room,
                    message=message,
                    pinned_by=request.user
                )
                return Response({
                    'success': True, 
                    'pinned': True,
                    'message': 'Message pinned'
                }, status=status.HTTP_201_CREATED)
                
        except Message.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class GetPinnedMessagesView(generics.ListAPIView):
    """Get all pinned messages in a room"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return Message.objects.filter(
            pinnedmessage__room_id=room_id
        ).order_by('-pinnedmessage__pinned_at')