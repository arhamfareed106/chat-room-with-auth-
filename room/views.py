from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Room
# Create your views here.

@login_required
def rooms(request):
    rooms = Room.objects.all()
    return render(request, 'room/rooms.html', {'rooms': rooms}) 