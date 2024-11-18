from django.urls import path
from . import views

urlpatterns = [
    path('', views.rooms, name='rooms'),
    path('create/', views.create_room, name='create_room'),
    path('<slug:slug>/', views.room, name='room'),
    path('<slug:slug>/messages/', views.get_messages, name='get_messages'),
    path('<slug:slug>/send/', views.send_message, name='send_message'),
    path('<slug:slug>/invite/', views.invite_to_room, name='invite_to_room'),
    path('<slug:slug>/generate_invite_link/', views.generate_invite_link, name='generate_invite_link'),
    path('<slug:slug>/settings/', views.room_settings, name='room_settings'),
    path('<slug:slug>/leave/', views.leave_room, name='leave_room'),
    path('<slug:slug>/delete/', views.delete_room, name='delete_room'),
    path('search_users/', views.search_users, name='search_users'),
    path('my_invitations/', views.my_invitations, name='my_invitations'),
    path('accept_invitation/<uuid:code>/', views.accept_invitation, name='accept_invitation'),
    path('join/<uuid:code>/', views.join_room_via_invitation, name='join_room_via_invitation'),
    path('decline_invitation/<uuid:code>/', views.decline_invitation, name='decline_invitation'),
]
