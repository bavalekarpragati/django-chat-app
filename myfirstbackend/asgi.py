import os
import django
from django.core.asgi import get_asgi_application

# Initialize Django BEFORE importing other modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myfirstbackend.settings')
django.setup()  # This is critical!

# Now import channels and routing AFTER django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})
