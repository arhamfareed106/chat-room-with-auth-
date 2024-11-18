from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils.text import slugify
from .models import Room, Message, Invitation
from django.contrib.auth.models import User
from django.utils import timezone
import json
from datetime import timedelta

def generate_unique_slug(name):
    """Generate a unique slug for a room name."""
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    
    while Room.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug

@login_required
def rooms(request):
    """View for listing all rooms the user is part of."""
    rooms = Room.objects.filter(
        Q(participants=request.user) | Q(is_private=False)
    ).distinct()
    
    return render(request, 'room/rooms.html', {
        'rooms': rooms
    })

@login_required
def create_room(request):
    if request.method == 'POST':
        room_name = request.POST.get('name', '').strip()
        is_private = request.POST.get('is_private', 'true') == 'true'
        description = request.POST.get('description', '').strip()
        
        if room_name:
            # Create unique slug
            slug = generate_unique_slug(room_name)
            
            # Create room
            room = Room.objects.create(
                name=room_name,
                slug=slug,
                created_by=request.user,
                is_private=is_private,
                description=description
            )
            
            # Add creator as participant
            room.participants.add(request.user)
            
            # Add other participants if specified
            participant_usernames = request.POST.getlist('participants')
            if participant_usernames:
                participants = User.objects.filter(username__in=participant_usernames)
                room.participants.add(*participants)
            
            return redirect('room', slug=room.slug)
    
    # Get all users except the current user for the participant selection
    users = User.objects.exclude(id=request.user.id).order_by('username')
    return render(request, 'room/create_room.html', {'users': users})

@login_required
def room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    # Check if user has access to the room
    if room.is_private and request.user not in room.participants.all():
        messages.error(request, "You don't have access to this room.")
        return redirect('rooms')
    
    # Get messages for the room
    messages = Message.objects.filter(room=room).order_by('-date_added')
    # Get the last 50 messages and reverse them for display
    messages_to_display = messages[:50][::-1]
    
    # Get all rooms the user is part of
    other_rooms = Room.objects.filter(
        Q(participants=request.user) | Q(created_by=request.user)
    ).exclude(slug=slug).order_by('-last_activity')[:10]
    
    # Check if user is room admin
    is_room_admin = room.created_by == request.user
    
    # Check if user can invite others (admin or participant in private room)
    can_invite = is_room_admin or (room.is_private and request.user in room.participants.all())
    
    # Mark unread messages as read
    unread_messages = Message.objects.filter(
        room=room,
        is_read=False
    ).exclude(user=request.user)
    
    for message in unread_messages:
        message.mark_as_read(request.user)
    
    # Get online participants
    online_participants = room.get_online_participants()
    
    return render(request, 'room/room.html', {
        'room': room,
        'messages': messages_to_display,
        'other_rooms': other_rooms,
        'is_room_admin': is_room_admin,
        'can_invite': can_invite,
        'participants': room.participants.all(),
        'online_participants': online_participants,
    })

@login_required
def send_message(request, slug):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            content = data.get('message', '').strip()
            
            if content:
                room = get_object_or_404(Room, slug=slug)
                message = Message.objects.create(
                    room=room,
                    user=request.user,
                    content=content
                )
                
                # Update room's last activity
                room.last_activity = timezone.now()
                room.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'username': message.user.username,
                        'timestamp': message.date_added.isoformat(),
                        'is_read': False,
                        'read_by_count': 0
                    }
                })
                
        except json.JSONDecodeError:
            pass
            
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def get_messages(request, slug):
    room = get_object_or_404(Room, slug=slug)
    before_id = request.GET.get('before_id')
    
    messages_query = Message.objects.filter(room=room)
    
    if before_id:
        messages_query = messages_query.filter(id__lt=before_id)
    
    messages = messages_query.order_by('-date_added')[:20]
    
    messages_data = [{
        'id': msg.id,
        'content': msg.content,
        'username': msg.user.username,
        'timestamp': msg.date_added.isoformat(),
        'is_read': msg.is_read,
        'read_by_count': msg.read_by_users.count()
    } for msg in messages]
    
    return JsonResponse({'messages': messages_data})

@login_required
def mark_as_read(request, slug):
    if request.method == 'POST':
        room = get_object_or_404(Room, slug=slug)
        message_ids = json.loads(request.body).get('message_ids', [])
        
        if message_ids:
            messages = Message.objects.filter(
                room=room,
                id__in=message_ids,
                is_read=False
            ).exclude(user=request.user)
            
            for message in messages:
                message.mark_as_read(request.user)
                
        return JsonResponse({'status': 'success'})
        
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def join_room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    if not room.is_private:
        room.participants.add(request.user)
        messages.success(request, f'You have joined the room: {room.name}')
        return redirect('room', slug=room.slug)
    else:
        messages.error(request, 'This is a private room. You need an invitation to join.')
        return redirect('rooms')

@login_required
def load_more_messages(request, slug):
    """AJAX view for loading older messages."""
    room = get_object_or_404(Room, slug=slug)
    
    if request.user not in room.participants.all():
        return JsonResponse({'status': 'error', 'message': 'Not authorized'})
    
    try:
        last_message_id = request.GET.get('last_message_id')
        messages_queryset = Message.objects.filter(
            room=room,
            id__lt=last_message_id
        ).select_related('user')\
            .order_by('-date_added')[:20]
        
        messages_data = [{
            'id': msg.id,
            'content': msg.content,
            'username': msg.user.username,
            'timestamp': msg.date_added.isoformat(),
            'is_own_message': msg.user == request.user
        } for msg in messages_queryset]
        
        return JsonResponse({
            'status': 'success',
            'messages': messages_data,
            'has_more': messages_queryset.exists() and \
                Message.objects.filter(room=room, id__lt=messages_queryset.last().id).exists()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def invite_to_room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    # Check if user has permission to invite
    if not (request.user == room.created_by or request.user in room.participants.all()):
        return JsonResponse({'status': 'error', 'message': 'You do not have permission to invite users to this room.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            usernames = data.get('usernames', [])
            
            successful_invites = []
            failed_invites = []
            
            for username in usernames:
                try:
                    user = User.objects.get(username=username)
                    
                    # Check if user is already in the room
                    if user in room.participants.all():
                        failed_invites.append({'username': username, 'reason': 'Already in room'})
                        continue
                    
                    # Check if invitation already exists
                    if Invitation.objects.filter(room=room, invited_user=user, accepted=False).exists():
                        failed_invites.append({'username': username, 'reason': 'Invitation pending'})
                        continue
                    
                    # Create invitation
                    invitation = Invitation.objects.create(
                        room=room,
                        invited_by=request.user,
                        invited_user=user
                    )
                    successful_invites.append({
                        'username': username,
                        'invite_code': invitation.invite_code
                    })
                    
                except User.DoesNotExist:
                    failed_invites.append({'username': username, 'reason': 'User not found'})
            
            return JsonResponse({
                'status': 'success',
                'successful_invites': successful_invites,
                'failed_invites': failed_invites
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def accept_invitation(request, code):
    invitation = get_object_or_404(Invitation, invite_code=code)
    
    # Check if invitation has expired
    if invitation.is_expired():
        return render(request, 'room/invitation_error.html', {
            'error': 'This invitation has expired.'
        })
    
    # Check if user is the invited user
    if invitation.invited_user != request.user:
        return render(request, 'room/invitation_error.html', {
            'error': 'This invitation is not for you.'
        })
    
    # Check if already accepted
    if invitation.accepted:
        return redirect('room', slug=invitation.room.slug)
    
    # Accept invitation
    invitation.accepted = True
    invitation.save()
    
    # Add user to room
    invitation.room.participants.add(request.user)
    
    return redirect('room', slug=invitation.room.slug)

@login_required
def my_invitations(request):
    # Get pending invitations for the user
    pending_invitations = Invitation.objects.filter(
        invited_user=request.user,
        accepted=False
    ).select_related('room', 'invited_by').order_by('-created_at')
    
    return render(request, 'room/my_invitations.html', {
        'invitations': pending_invitations
    })

@login_required
def generate_invite_link(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    # Check if user has permission to generate invite link
    if not (request.user == room.created_by or request.user in room.participants.all()):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    # Create an open invitation (no specific invited user)
    invitation = Invitation.objects.create(
        room=room,
        invited_by=request.user,
        invited_user=None  # This makes it an open invitation
    )
    
    invite_url = request.build_absolute_uri(f'/rooms/join/{invitation.invite_code}/')
    
    return JsonResponse({
        'status': 'success',
        'invite_url': invite_url,
        'invite_code': str(invitation.invite_code)
    })

@login_required
def join_room_via_invitation(request, code):
    invitation = get_object_or_404(Invitation, invite_code=code)
    
    # Check if invitation has expired
    if invitation.is_expired():
        return render(request, 'room/invitation_error.html', {
            'error': 'This invitation has expired.'
        })
    
    # If it's an open invitation (no specific invited user)
    if invitation.invited_user is None:
        # Check if user is already in the room
        if request.user in invitation.room.participants.all():
            return redirect('room', slug=invitation.room.slug)
        
        # Add user to room
        invitation.room.participants.add(request.user)
        return redirect('room', slug=invitation.room.slug)
    
    return render(request, 'room/invitation_error.html', {
        'error': 'This invitation is for a specific user.'
    })

@login_required
def leave_room(request, slug):
    """View for leaving a chat room."""
    room = get_object_or_404(Room, slug=slug)
    
    if request.user == room.created_by:
        messages.error(request, 'Room creator cannot leave the room.')
        return redirect('room', slug=slug)
    
    if request.user in room.participants.all():
        room.participants.remove(request.user)
        messages.success(request, f'You have left the room: {room.name}')
    
    return redirect('rooms')

@login_required
def delete_room(request, slug):
    """View for deleting a chat room."""
    room = get_object_or_404(Room, slug=slug)
    
    if request.user != room.created_by:
        messages.error(request, 'Only room creator can delete the room.')
        return redirect('room', slug=slug)
    
    if request.method == 'POST':
        room_name = room.name
        room.delete()
        messages.success(request, f'Room "{room_name}" has been deleted.')
        return redirect('rooms')
    
    return render(request, 'room/delete_room.html', {'room': room})

@login_required
def room_settings(request, slug):
    """View for managing room settings."""
    room = get_object_or_404(Room, slug=slug)
    
    if request.user != room.created_by:
        messages.error(request, 'Only room creator can modify settings.')
        return redirect('room', slug=slug)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        is_private = request.POST.get('is_private') == 'on'
        
        if name:
            room.name = name
            room.is_private = is_private
            room.save()
            messages.success(request, 'Room settings updated successfully.')
            return redirect('room', slug=room.slug)
        else:
            messages.error(request, 'Room name is required.')
    
    return render(request, 'room/room_settings.html', {'room': room})

@login_required
def search_users(request):
    """Search for users to invite to a room."""
    query = request.GET.get('q', '').strip()
    
    if query:
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id
        ).values('username')[:10]
    else:
        users = User.objects.exclude(
            id=request.user.id
        ).values('username')[:10]
    
    return JsonResponse({'users': list(users)})

@login_required
def decline_invitation(request, code):
    """Decline a room invitation."""
    if request.method == 'POST':
        invitation = get_object_or_404(
            Invitation,
            invite_code=code,
            invited_user=request.user,
            accepted=False
        )
        
        # Delete the invitation
        invitation.delete()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
