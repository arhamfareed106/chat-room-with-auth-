from django.urls import path
from . import views

urlpatterns = [
    path('', views.rooms, name='rooms'),
    path('create/', views.create_room, name='create-room'),
    path('<slug:slug>/', views.room, name='room'),
    path('<slug:slug>/invite/', views.invite_user, name='invite-user'),
    path('<slug:slug>/generate-invite/', views.generate_invite_link, name='generate-invite'),
    path('join/<uuid:invite_code>/', views.join_room, name='join-room'),
    path('<slug:slug>/invite-from-room/', views.invite_from_room, name='invite-from-room'),
    path('<slug:slug>/get-room-members/', views.get_room_members, name='get-room-members'),
]
