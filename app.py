import os
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'skyos-chat-secret')
socketio = SocketIO(app, cors_allowed_origins="*")

# Хранилище: sid -> {'username': str, 'rooms': set}
users = {}
# Для личных сообщений не нужны комнаты, будем отправлять по sid получателя
# Для поиска username -> sid
username_to_sid = {}

@app.route('/')
def index():
    return "SkyOS Chat Server is running!"

@app.route('/health')
def health():
    return {"status": "ok", "users": len(users)}, 200

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in users:
        username = users[sid]['username']
        # Удаляем из словаря
        if username in username_to_sid and username_to_sid[username] == sid:
            del username_to_sid[username]
        del users[sid]
        # Уведомляем общий чат
        emit('user_left', {'username': username}, room='general', skip_sid=sid)
        print(f"User {username} disconnected")

@socketio.on('register')
def handle_register(data):
    """Регистрация пользователя (установка username)."""
    sid = request.sid
    username = data.get('username', '').strip()
    if not username:
        emit('register_error', {'message': 'Username cannot be empty'})
        return
    if username in username_to_sid:
        emit('register_error', {'message': 'Username already taken'})
        return
    # Сохраняем
    users[sid] = {'username': username}
    username_to_sid[username] = sid
    join_room('general', sid=sid)
    # Отправляем подтверждение
    emit('registered', {'username': username})
    # Отправляем список онлайн пользователей новому пользователю
    online_users = list(username_to_sid.keys())
    emit('user_list', online_users, to=sid)
    # Уведомляем всех в общем чате
    emit('user_joined', {'username': username}, room='general', skip_sid=sid)
    print(f"User {username} registered with sid {sid}")

@socketio.on('message')
def handle_message(data):
    """Обработка сообщения в общий чат."""
    sid = request.sid
    if sid not in users:
        return
    username = users[sid]['username']
    text = data.get('text', '')
    timestamp = datetime.now().isoformat()
    emit('message', {
        'username': username,
        'text': text,
        'timestamp': timestamp,
        'type': 'public'
    }, room='general', include_self=True)  # включая отправителя

@socketio.on('private_message')
def handle_private_message(data):
    """Отправка личного сообщения."""
    sid = request.sid
    if sid not in users:
        return
    from_username = users[sid]['username']
    to_username = data.get('to')
    text = data.get('text', '')
    if not to_username or to_username not in username_to_sid:
        emit('private_error', {'message': 'User not found or offline'})
        return
    to_sid = username_to_sid[to_username]
    timestamp = datetime.now().isoformat()
    # Отправляем получателю
    emit('private_message', {
        'from': from_username,
        'text': text,
        'timestamp': timestamp
    }, room=to_sid)
    # Отправляем подтверждение отправителю (опционально)
    emit('private_sent', {
        'to': to_username,
        'text': text,
        'timestamp': timestamp
    }, room=sid)

@socketio.on('get_online_users')
def handle_get_online_users():
    sid = request.sid
    online = list(username_to_sid.keys())
    emit('user_list', online, to=sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
