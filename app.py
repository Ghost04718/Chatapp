from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Association table for many-to-many relationship between users and rooms
user_rooms = db.Table('user_rooms',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('room_id', db.Integer, db.ForeignKey('room.id'), primary_key=True)
)

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    image = db.Column(db.String(120), nullable=True)
    messages = db.relationship('Message', backref='user', lazy=True)
    rooms = db.relationship('Room', secondary=user_rooms, back_populates='users')

# Room model
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('Message', backref='room', lazy=True)
    users = db.relationship('User', secondary=user_rooms, back_populates='rooms')
    is_public = db.Column(db.Boolean, default=False)

# Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registration form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=150)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

# Login form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Initialize the database
with app.app_context():
    try:
        db.drop_all()  # Comment out this line in production
        db.create_all()
        hashed_password = generate_password_hash('your_secret_key')
        new_user = User(username='Chatbot', password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Chat route
@app.route('/chat')
@login_required
def chat():
    public_rooms = Room.query.filter_by(is_public=True).all()
    user_rooms = current_user.rooms
    rooms = list(set(public_rooms + user_rooms))
    return render_template('chat.html', rooms=rooms)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('register'))
        
        # Register new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            print(f"Error: {str(e)}")
            return redirect(url_for('register'))

    return render_template('register.html', form=form)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('chat'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Send message route
@app.route('/send_message/<int:room_id>', methods=['POST'])
@login_required
def send_message(room_id):
    content = request.form.get('content')
    if content:
        new_message_user = Message(user_id=current_user.id, room_id=room_id, content=content)
        db.session.add(new_message_user)
        db.session.commit()
        if content.startswith('@Chatbot'):
            messages = Message.query.filter_by(room_id=room_id).order_by(Message.id.asc()).all()
            messages_string = " ".join([message.content for message in messages])
            prompt = content.replace('@Chatbot', '', 1).strip()
            reponse = get_chatbot_response(messages_string, prompt)  # Get response from chatbot
            new_message_chatbot = Message(user_id=1, room_id=room_id, content=reponse)
            db.session.add(new_message_chatbot)
            db.session.commit()
    return redirect(url_for('room_chat', room_id=room_id))

# Route to get started with chat rooms
@app.route('/get_started')
def get_started():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('register'))

# Chat room route for individual rooms
@app.route('/chat/<int:room_id>')
@login_required
def room_chat(room_id):
    room = Room.query.get_or_404(room_id)
    
    # Automatically add the user to the room if it's public and they are not a member
    if room.is_public and room not in current_user.rooms:
        current_user.rooms.append(room)
        db.session.commit()
    
    messages = Message.query.filter_by(room_id=room_id).order_by(Message.id.asc()).all()  # Order messages
    return render_template('room_chat.html', room=room, messages=messages, current_user=current_user)

# Route to create a room
@app.route('/create_room', methods=['GET', 'POST'])
@login_required
def create_room():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        is_public = request.form.get('is_public') == 'on'

        # Check if room already exists
        existing_room = Room.query.filter_by(name=room_name).first()
        if existing_room:
            flash('Chatroom already exists. Please name a different one.', 'error')
            return render_template('create_room.html')

        if room_name:
            new_room = Room(name=room_name, created_by=current_user.id, is_public=is_public)
            new_room.users.append(current_user)
            db.session.add(new_room)
            db.session.commit()
            flash('Room created successfully!', 'success')
            return redirect(url_for('chat'))
    return render_template('create_room.html')

# Route to join a room
@app.route('/join_room', methods=['GET', 'POST'])
@login_required
def join_room():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        room = Room.query.filter_by(name=room_name).first()
        if room and room not in current_user.rooms:
            current_user.rooms.append(room)
            db.session.commit()
            flash('Joined room successfully!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('Room not found or you are already a member.', 'error')
    return render_template('join_room.html')

# Route to quit a room
@app.route('/quit_room/<int:room_id>', methods=['POST'])
@login_required
def quit_room(room_id):
    room = Room.query.get_or_404(room_id)
    
    # Remove the user from the room
    if room in current_user.rooms:
        current_user.rooms.remove(room)
        db.session.commit()
        
        # If the room has no more users and not public, delete it
        if not room.users and not room.is_public:
            db.session.delete(room)
            db.session.commit()
        
        flash('You have left the room.', 'success')
    else:
        flash('You are not a member of this room.', 'error')
    
    return redirect(url_for('chat'))

# API to return graph data (users, rooms, and messages)
@app.route('/graph_data')
@login_required
def graph_data():
    current_user_id = current_user.id
    
    # Fetch the chatrooms the current user is a part of
    user_chatrooms = Room.query.filter(Room.users.any(id=current_user_id)).all()
    
    # Initialize nodes and links
    nodes = []
    links = []
    
    added_users_nodes = {}
    added_rooms_nodes = {}

    # Add the current user as a node
    nodes.append({"id": f"user_{current_user.id}", "name": current_user.username, "group": "current_user", "size": 10})  # Example size
    added_users_nodes[current_user_id] = 1  # Track appearance count

    for chatroom in user_chatrooms:
        # Add chatroom node
        nodes.append({"id": f"room_{chatroom.id}", "name": chatroom.name, "group": "chatroom", "size": 10})  # Default size
        added_rooms_nodes[chatroom.id] = True  # Mark as added
        
        # Add users in the chatroom as nodes and links
        for user in chatroom.users:
            # Track user appearance count
            if user.id not in added_users_nodes:
                added_users_nodes[user.id] = 1  # Initialize count
                nodes.append({"id": f"user_{user.id}", "name": user.username, "group": "user", "size": 10})  # Default size
            else:
                added_users_nodes[user.id] += 1  # Increment count
            
            # Create link between user and chatroom
            links.append({"source": f"user_{user.id}", "target": f"room_{chatroom.id}"})

    # Update sizes based on appearance count
    for user_id, count in added_users_nodes.items():
        for node in nodes:
            if node['id'] == f"user_{user_id}":
                node['size'] += count * 2

    # Constructing the graph data
    graph_data = {
        "nodes": nodes,
        "links": links
    }

    return jsonify(graph_data)  # Ensure to return JSON data



@app.route('/graph')
@login_required
def graph():
    return render_template('graph.html')


if __name__ == '__main__':
    app.run(debug=True)
