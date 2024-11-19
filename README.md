# Django Real-Time Chat Application

A modern, feature-rich chat application built with Django and WebSockets, featuring real-time messaging, private rooms, and user authentication.

## Features

- **User Authentication**: Secure signup and login functionality
- **Real-time Messaging**: Instant message delivery using WebSocket technology
- **Chat Rooms**: Create and join public or private chat rooms
- **Room Management**: 
  - Create new chat rooms
  - Join existing rooms
  - Leave rooms
  - Delete rooms (room creator only)
- **Invitation System**:
  - Send invitations to users for private rooms
  - Accept/decline room invitations
  - Invitation expiration system
- **Real-time Features**:
  - Online user status
  - Typing indicators
  - Message read status
  - Participant count
- **Modern UI**: Clean and responsive design using Tailwind CSS

## Technology Stack

- **Backend**: Django 5.1.3
- **WebSocket**: Django Channels 4.1.0
- **Database**: SQLite (easily adaptable to other databases)
- **Frontend**: 
  - HTML/CSS/JavaScript
  - Tailwind CSS for styling
  - WebSocket for real-time communication

## Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd djangochat
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Start the development server:
```bash
python manage.py runserver
```

5. Visit `http://localhost:8000` in your browser

## Project Structure

- `core/` - Core application with authentication views and templates
- `room/` - Chat room functionality including models, views, and templates
- `djangochat/` - Project settings and configuration
- `templates/` - HTML templates for the application
- `static/` - Static files (CSS, JavaScript, images)

## Features in Detail

### Room Management
- Create public or private chat rooms
- Join rooms through invitations (for private rooms)
- Leave rooms at any time
- Room creators can manage room settings and delete rooms

### Real-time Chat
- Instant message delivery
- Typing indicators
- Online/offline user status
- Message read receipts
- User presence detection

### User Management
- User registration and authentication
- User profile management
- Online status tracking
- User search functionality

### Invitation System
- Generate invitation links
- Send direct invitations to users
- Time-limited invitations
- Accept/decline invitation functionality

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Django Framework
- Django Channels
- Tailwind CSS
- All contributors who have helped to improve this project
