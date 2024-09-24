from flask import Flask, render_template, redirect, url_for, request, flash
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

# Add this new association table
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
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

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
    db.drop_all()  # This will drop all existing tables
    db.create_all()  # This will create all tables based on your current models

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
        
        # If user doesn't exist, proceed with registration
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
        new_message = Message(user_id=current_user.id, room_id=room_id, content=content)
        db.session.add(new_message)
        db.session.commit()
    return redirect(url_for('room_chat', room_id=room_id))

# Get Started route (for chat rooms)
@app.route('/get_started')
def get_started():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('register'))

# New route for individual room chats
@app.route('/chat/<int:room_id>')
@login_required
def room_chat(room_id):
    room = Room.query.get_or_404(room_id)
    messages = Message.query.filter_by(room_id=room_id).order_by(Message.timestamp.asc()).all()
    return render_template('room_chat.html', room=room, messages=messages)

# Add this new route
@app.route('/create_room', methods=['GET', 'POST'])
@login_required
def create_room():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        is_public = request.form.get('is_public') == 'on'
        if room_name:
            new_room = Room(name=room_name, created_by=current_user.id, is_public=is_public)
            new_room.users.append(current_user)
            db.session.add(new_room)
            db.session.commit()
            flash('Room created successfully!', 'success')
            return redirect(url_for('chat'))
    return render_template('create_room.html')

# Add this new route
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

if __name__ == '__main__':
    app.run(debug=True)