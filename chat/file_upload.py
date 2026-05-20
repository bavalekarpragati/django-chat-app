# chat/file_upload.py
import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request):
    """Handle file uploads for chat"""
    
    # Check if file exists in request
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    uploaded_file = request.FILES['file']
    
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if uploaded_file.size > max_size:
        return Response(
            {'error': f'File too large. Max size is 10MB'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Generate unique filename
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    
    # Determine file type
    file_type = 'file'
    if uploaded_file.content_type.startswith('image/'):
        file_type = 'image'
    elif uploaded_file.content_type.startswith('video/'):
        file_type = 'video'
    elif uploaded_file.content_type.startswith('audio/'):
        file_type = 'audio'
    elif uploaded_file.content_type == 'application/pdf':
        file_type = 'document'
    
    # Save file
    file_path = default_storage.save(
        f'chat_uploads/{unique_filename}', 
        uploaded_file
    )
    
    # Return file information
    return Response({
        'success': True,
        'file_url': default_storage.url(file_path),
        'file_name': uploaded_file.name,
        'file_size': uploaded_file.size,
        'file_type': file_type,
        'mime_type': uploaded_file.content_type,
        'message': f'File uploaded successfully'
    }, status=status.HTTP_201_CREATED)