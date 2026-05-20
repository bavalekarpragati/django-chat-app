from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chat/', include('chat.urls')),  # Add 'chat/' prefix here
    path('', include('chat.urls')),  # This sends root URL to your chat app
    path('api/auth/', include('accounts.urls')),  # Auth endpoints
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)