# chat/urls.py
from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Web page views (work at both / and /chat/)
    path('', views.index, name='index'),
    path('room/<str:room_name>/', views.room, name='room'),
    
    # API views (work at both /api/ and /chat/api/)
    path('api/health/', views.health_check, name='api-health'),
    path('api/rooms/', views.RoomListCreateView.as_view(), name='api-rooms'),
    path('api/rooms/<int:pk>/', views.RoomDetailView.as_view(), name='api-room-detail'),
    path('api/rooms/<int:room_id>/messages/', views.RoomMessagesView.as_view(), name='api-room-messages'),
    path('api/rooms/<int:room_id>/messages/create/', views.MessageCreateView.as_view(), name='api-create-message'),
    path('api/rooms/<int:room_id>/members/', views.RoomMembersView.as_view(), name='api-room-members'),
    path('api/rooms/<int:room_id>/join/', views.JoinRoomView.as_view(), name='api-join-room'),
    path('api/rooms/<int:room_id>/leave/', views.LeaveRoomView.as_view(), name='api-leave-room'),
    path('api/rooms/<int:room_id>/search/', views.SearchMessagesView.as_view(), name='api-search-messages'),
    path('api/my-rooms/', views.UserRoomsView.as_view(), name='api-my-rooms'),
    path('api/stats/', views.get_chat_stats, name='api-stats'),
    path('login/', TemplateView.as_view(template_name='accounts/login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='accounts/register.html'), name='register'),
]