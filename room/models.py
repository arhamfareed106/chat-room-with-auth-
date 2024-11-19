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
    date_added = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_by_users = models.ManyToManyField(User, related_name='read_messages', blank=True)
    target_user = models.ForeignKey(
        User, 
        related_name='targeted_messages', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    is_targeted = models.BooleanField(default=False)

    def mark_as_read(self, user):
        if user not in self.read_by_users.all():
            self.read_by_users.add(user)
            if self.read_by_users.count() == self.room.participants.count():
                self.is_read = True
                self.save()

    class Meta:
        ordering = ['-date_added']

    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}'

class Invitation(models.Model):
    INVITATION_STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    status = models.CharField(max_length=20, choices=INVITATION_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  
    is_email_sent = models.BooleanField(default=False)
    invitation_code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    def __str__(self):
        return f'Invitation to {self.room.name} for {self.invited_user.username}'

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
