from django.urls import path
from . import views

urlpatterns = [
    path('', views.rooms, name='rooms'),
    path('create/', views.create_room, name='create-room'),
    path('join/<str:slug>/', views.join_room, name='join-room'),
    path('<str:slug>/', views.room, name='room'),
    path('<slug:slug>/settings/', views.room_settings, name='room-settings'),
    path('<slug:slug>/delete/', views.delete_room, name='delete-room'),
    path('<slug:slug>/leave/', views.leave_room, name='leave-room'),
    path('<slug:slug>/invite/', views.invite_user, name='invite-user'),
]
