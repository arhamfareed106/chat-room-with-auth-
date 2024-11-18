from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib import messages
from .models import Room, Message, Invitation
from django.utils.text import slugify
from django.db.models import Q
import uuid
from django.urls import reverse
from django.conf import settings

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
    rooms = Room.objects.filter(participants=request.user)
    invitations = Invitation.objects.filter(invited_user=request.user, accepted=False)
    return render(request, 'room/rooms.html', {
        'rooms': rooms,
        'invitations': invitations
    })

@login_required
def create_room(request):
    if request.method == 'POST':
        room_name = request.POST.get('room_name')
        if room_name:
            # Generate a unique slug
            slug = generate_unique_slug(room_name)
            
            # Create the room with the unique slug
            room = Room.objects.create(
                name=room_name, 
                slug=slug,
                created_by=request.user
            )
            room.participants.add(request.user)
            return redirect('room', slug=slug)
    return render(request, 'room/create_room.html')

@login_required
def room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    
    # Check if user is a participant
    if request.user not in room.participants.all():
        invitation = Invitation.objects.filter(
            Q(room=room) & 
            (Q(invited_user=request.user) | Q(invited_user__isnull=True)),
            accepted=False
        ).first()
        
        if invitation:
            if request.method == 'POST' and 'accept_invitation' in request.POST:
                invitation.accepted = True
                invitation.invited_user = request.user
                invitation.save()
                room.participants.add(request.user)
            else:
                return render(request, 'room/invitation_prompt.html', {'invitation': invitation})
        else:
            messages.error(request, "You don't have access to this room.") # type: ignore
            return redirect('rooms')

    # Handle message posting
    if request.method == 'POST' and 'content' in request.POST:
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                room=room,
                user=request.user,
                content=content
            )
            return redirect('room', slug=slug)

    # Get all messages for the room
    chat_messages = Message.objects.filter(room=room).select_related('user').order_by('date_added')
    users = User.objects.exclude(id=request.user.id).exclude(chat_rooms=room)
    
    # Get other rooms where the user is a participant
    other_rooms = Room.objects.filter(participants=request.user).exclude(id=room.id) # type: ignore
    
    return render(request, 'room/room.html', {
        'room': room,
        'messages': chat_messages,
        'users': users,
        'other_rooms': other_rooms,
        'current_user': request.user
    })

@login_required
def generate_invite_link(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user not in room.participants.all():
        return JsonResponse({'status': 'error', 'message': 'You are not a participant of this room'})
    
    # Create an invitation without a specific user
    invitation = Invitation.objects.create(
        room=room,
        invited_by=request.user,
        invited_user=None
    )
    
    # Generate the invitation link
    invite_url = request.build_absolute_uri(
        reverse('join-room', kwargs={'invite_code': invitation.invite_code})
    )
    
    return JsonResponse({
        'status': 'success',
        'invite_link': invite_url,
        'message': 'Invitation link generated successfully'
    })

@login_required
def join_room(request, invite_code):
    invitation = get_object_or_404(Invitation, invite_code=invite_code, accepted=False)
    
    # Check if the invitation is already used
    if invitation.invited_user and invitation.invited_user != request.user:
        messages.error(request, "This invitation has already been used by another user.") # type: ignore
        return redirect('rooms')
    
    if request.method == 'POST':
        invitation.accepted = True
        invitation.invited_user = request.user
        invitation.save()
        
        invitation.room.participants.add(request.user)
        messages.success(request, f"You have joined the room: {invitation.room.name}") # type: ignore
        return redirect('room', slug=invitation.room.slug)
    
    return render(request, 'room/join_room.html', {
        'invitation': invitation
    })

@login_required
def invite_user(request, slug):
    if request.method == 'POST':
        room = get_object_or_404(Room, slug=slug)
        if request.user not in room.participants.all():
            return JsonResponse({'status': 'error', 'message': 'You are not a participant of this room'})
        
        user_id = request.POST.get('user_id')
        if user_id:
            invited_user = get_object_or_404(User, id=user_id)
            if invited_user not in room.participants.all():
                invitation = Invitation.objects.create(
                    room=room,
                    invited_by=request.user,
                    invited_user=invited_user
                )
                return JsonResponse({
                    'status': 'success',
                    'message': f'Invitation sent to {invited_user.username}',
                    'invite_link': request.build_absolute_uri(
                        reverse('join-room', kwargs={'invite_code': invitation.invite_code})
                    )
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'User is already a participant'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def get_room_members(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user not in room.participants.all():
        return JsonResponse({'status': 'error', 'message': 'Access denied'})
    
    members = list(room.participants.values('id', 'username').exclude(id=request.user.id))
    return JsonResponse({
        'status': 'success',
        'members': members
    })

@login_required
def invite_from_room(request, slug):
    if request.method == 'POST':
        target_room = get_object_or_404(Room, slug=slug)
        source_room_id = request.POST.get('source_room_id')
        selected_users = request.POST.getlist('selected_users[]')
        
        # Verify permissions
        if request.user not in target_room.participants.all():
            return JsonResponse({'status': 'error', 'message': 'You are not a participant of the target room'})
        
        source_room = get_object_or_404(Room, id=source_room_id)
        if request.user not in source_room.participants.all():
            return JsonResponse({'status': 'error', 'message': 'You are not a participant of the source room'})
        
        # Send invitations
        success_count = 0
        already_member_count = 0
        for user_id in selected_users:
            try:
                user = User.objects.get(id=user_id)
                if user in target_room.participants.all():
                    already_member_count += 1
                    continue
                    
                Invitation.objects.get_or_create(
                    room=target_room,
                    invited_by=request.user,
                    invited_user=user
                )
                success_count += 1
            except User.DoesNotExist:
                continue
        
        message = f'Successfully invited {success_count} users'
        if already_member_count > 0:
            message += f' ({already_member_count} were already members)'
            
        return JsonResponse({
            'status': 'success',
            'message': message
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})
