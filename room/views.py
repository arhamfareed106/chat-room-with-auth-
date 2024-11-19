from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils.text import slugify
from .models import Room, Message, Invitation
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib import messages
import json
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

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
            slug = generate_unique_slug(room_name)
            
            room = Room.objects.create(
                name=room_name,
                slug=slug,
                created_by=request.user,
                is_private=is_private,
                description=description
            )
            
            room.participants.add(request.user)
            
            participant_usernames = request.POST.getlist('participants')
            if participant_usernames:
                participants = User.objects.filter(username__in=participant_usernames)
                room.participants.add(*participants)
            
            return redirect('room', slug=room.slug)
    
    users = User.objects.exclude(id=request.user.id).order_by('username')
    return render(request, 'room/create_room.html', {'users': users})

@login_required
def room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    if room.is_private and request.user not in room.participants.all():
        invitation = Invitation.objects.filter(
            room=room,
            invited_user=request.user,
            status='pending'
        ).first()
        
        if invitation:
            return render(request, 'room/invitation.html', {
                'invitation': invitation,
                'room': room
            })
        
        messages.error(request, "You don't have access to this room.")
        return redirect('rooms')
    
    room_messages = Message.objects.filter(room=room).order_by('-date_added')[:50][::-1]
    
    other_rooms = Room.objects.filter(
        Q(participants=request.user) | Q(created_by=request.user)
    ).exclude(slug=slug).order_by('-last_activity')[:10]
    
    is_room_admin = room.created_by == request.user
    can_invite = is_room_admin or (room.is_private and request.user in room.participants.all())
    
    # Mark unread messages as read
    unread_messages = Message.objects.filter(
        room=room,
        is_read=False
    ).exclude(user=request.user)
    
    for message in unread_messages:
        message.mark_as_read(request.user)
    
    online_participants = room.get_online_participants()
    
    return render(request, 'room/room.html', {
        'room': room,
        'messages': room_messages,
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
def handle_invitation(request, code):
    invitation = get_object_or_404(Invitation, code=code)
    
    if invitation.is_expired():
        invitation.status = 'expired'
        invitation.save()
        messages.error(request, 'This invitation has expired.')
        return JsonResponse({'status': 'error', 'message': 'Invitation has expired'})
    
    if invitation.status != 'pending':
        messages.error(request, 'This invitation is no longer valid.')
        return JsonResponse({'status': 'error', 'message': 'Invalid invitation'})
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'accept':
                invitation.room.participants.add(request.user)
                invitation.status = 'accepted'
                invitation.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Invitation accepted successfully',
                    'redirect_url': reverse('room', kwargs={'slug': invitation.room.slug})
                })
                
            elif action == 'decline':
                invitation.status = 'declined'
                invitation.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Invitation declined'
                })
            
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid action'
            })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request format'
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })

@login_required
def invite_by_username(request, room_slug):
    if request.method == 'POST':
        room = get_object_or_404(Room, slug=room_slug)
        if request.user != room.created_by and not room.participants.filter(id=request.user.id).exists():
            return JsonResponse({'status': 'error', 'message': 'You do not have permission to invite users to this room.'})

        data = json.loads(request.body)
        
        # Handle generate link request
        if data.get('generate_link'):
            invitation = Invitation.objects.create(
                room=room,
                invited_by=request.user,
                status='pending',
                expires_at=timezone.now() + timezone.timedelta(days=7)
            )
            
            invite_url = reverse('handle_invitation', kwargs={'code': str(invitation.code)})
            return JsonResponse({
                'status': 'success',
                'invite_url': invite_url,
                'message': 'Invite link generated successfully.'
            })
        
        # Handle username invitation
        username = data.get('username')
        if not username:
            return JsonResponse({'status': 'error', 'message': 'Username is required.'})

        try:
            invited_user = User.objects.get(username=username)
            
            if room.participants.filter(id=invited_user.id).exists():
                return JsonResponse({'status': 'error', 'message': f'{username} is already in this room.'})
            
            if Invitation.objects.filter(room=room, invited_user=invited_user, status='pending').exists():
                return JsonResponse({'status': 'error', 'message': f'An invitation for {username} is already pending.'})
            
            invitation = Invitation.objects.create(
                room=room,
                invited_by=request.user,
                invited_user=invited_user,
                status='pending',
                expires_at=timezone.now() + timezone.timedelta(days=7)
            )

            return JsonResponse({
                'status': 'success',
                'message': f'Invitation sent to {username}.',
                'invitation': {
                    'id': invitation.id,
                    'code': str(invitation.code),
                    'invited_username': invited_user.username
                }
            })
            
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'User {username} not found.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@login_required
def leave_room(request, slug):
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
def my_invitations(request):
    """View for displaying user's pending invitations."""
    invitations = Invitation.objects.filter(
        invited_user=request.user,
        status='pending'
    ).select_related('room', 'inviting_user')
    
    # Return JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        invitations_data = [{
            'code': str(inv.code),
            'room_name': inv.room.name,
            'invited_by': inv.inviting_user.username,
            'created_at': inv.created_at.isoformat()
        } for inv in invitations]
        return JsonResponse({'invitations': invitations_data})
    
    # Return normal template response for direct visits
    return render(request, 'room/my_invitations.html', {
        'invitations': invitations
    })
