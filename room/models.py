from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
import uuid

class Room(models.Model):   
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    participants = models.ManyToManyField(User, related_name='chat_rooms', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms', null=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(auto_now=True)
    is_private = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_online_participants(self):
        """Get participants who were active in the last 15 minutes"""
        fifteen_minutes_ago = timezone.now() - timezone.timedelta(minutes=15)
        return self.participants.filter(last_login__gt=fifteen_minutes_ago)

class Message(models.Model):
    room = models.ForeignKey(Room, related_name='messages', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='messages', on_delete=models.CASCADE)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    read_by_users = models.ManyToManyField(User, related_name='read_messages', blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('date_added',)

    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}'

    def mark_as_read(self, user):
        if user != self.user:
            self.read_by_users.add(user)
            if not self.is_read:
                self.is_read = True
                self.save()

class Invitation(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    invite_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    class Meta:
        unique_together = ['room', 'invited_user']
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation to {self.room.name} for {self.invited_user.username if self.invited_user else 'anyone'}"

    def is_expired(self):
        """Check if the invitation has expired (7 days)"""
        return timezone.now() > self.created_at + timezone.timedelta(days=7)
