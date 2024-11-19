from django.urls import path
from . import views

urlpatterns = [
    path('', views.rooms, name='rooms'),
    path('create/', views.create_room, name='create_room'),
    path('<slug:slug>/', views.room, name='room'),
    path('<slug:slug>/messages/', views.get_messages, name='get_messages'),
    path('<slug:slug>/send/', views.send_message, name='send_message'),
    path('<slug:slug>/settings/', views.room_settings, name='room_settings'),
    path('<slug:slug>/leave/', views.leave_room, name='leave_room'),
    path('<slug:slug>/delete/', views.delete_room, name='delete_room'),
    path('search_users/', views.search_users, name='search_users'),
    path('my_invitations/', views.my_invitations, name='my_invitations'),
    path('<slug:room_slug>/invite_username/', views.invite_by_username, name='invite_by_username'),
    path('invitation/<uuid:code>/handle/', views.handle_invitation, name='handle_invitation'),
]
