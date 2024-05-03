# Import necessary modules

# Add time and sign everyone out after lunch
# In report write who was signed in
# try to get data to automatically update without manually refreshing it

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from flask_socketio import SocketIO
import time
from datetime import datetime, timezone, timedelta
import pytz
from pytz import timezone


data_hashmap = {}


# Initialize Flask application
app = Flask(__name__)
# Configure SQLite database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students_library.db'
# Initialize SQLAlchemy object

db = SQLAlchemy(app)
socketio = SocketIO(app)


def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    print("Value:", value)
    print("Type of Value:", type(value))
    
    if isinstance(value, str):
        try:
            # Convert the string to a datetime object
            value = datetime.fromisoformat(value)
        except ValueError:
            # If conversion fails, return the original value
            return value
    
    print("Value after conversion (if applicable):", value)
    
    if isinstance(value, datetime):
        # Convert the datetime object to UTC time zone
        value_utc = value.replace(tzinfo=pytz.utc)
        # Convert to the desired time zone (EST)
        est = pytz.timezone('America/New_York')
        value_est = value_utc.astimezone(est)
        return value_est.strftime(format)
    else:
        return ''


app.jinja_env.filters['datetimeformat'] = datetimeformat


# Define User and LibraryLog models
class User(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class LibraryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=False)
    time_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    time_out = db.Column(db.DateTime)

    # Define the relationship with the User model
    user = db.relationship('User', backref=db.backref('library_logs', lazy=True))

# Create tables in the database
with app.app_context():
    db.create_all()

# Function to load student data from CSV file into the database
def load_student_data():
    try:
        print("Attempting to load data from CSV file.")
        # Read data from CSV file into a pandas DataFrame
        data = pd.read_csv('C:\\Users\\24pierced\\Desktop\\BackendDataBase\\students_data.csv', delimiter=',')

        # Check if the DataFrame is empty
        if data.empty:
            print("Error: CSV file is empty.")
            return
        # Check if the DataFrame has columns
        if not data.columns.any():
            print("Error: CSV file does not have columns.")
            return

        print("Loaded Data:")

        # Iterate over each row in the DataFrame
        for _, row in data.iterrows():
            # Check if 'id_code' column exists in the row
            if 'id_code' in row:
                name = row['name']
                id_code = str(row['id_code'])
                data_hashmap[name] = id_code

                # Check if the user already exists in the User table
                user_exists = User.query.filter_by(id=id_code).first()
                if not user_exists:
                    # If not, add the user to the User table
                    new_user = User(id=id_code, name=name)
                    db.session.add(new_user)
                    db.session.commit()
            else:
                print(f"Warning: 'id_code' not found in the row #{row}.")

        for name, id_code in data_hashmap.items():
            print(f"Name: {name}, ID Code: {id_code}")

        print("Data loaded successfully.")
    except Exception as e:
        print(f"Error during data loading. Exception Type: {type(e).__name__}, Message: {e}")

# Endpoint for user sign-in
@app.route('/signin', methods=['POST'])
def signin():
    data = request.json
    user_id = data.get('user_id')

    user = User.query.get(user_id)
    if user:
        current_time_utc = datetime.now(timezone.utc)
        current_time_adjusted = current_time_utc - timedelta(hours = 4)
        log_entry = LibraryLog(user_id=user_id, time_in = current_time_adjusted)
        db.session.add(log_entry)
        db.session.commit()
        socketio.emit('refresh', namespace='/library')
        return jsonify(message=f"{user.name} signed in successfully."), 201
    else:
        return jsonify(error="User not found."), 404

# Endpoint for user sign-out
@app.route('/signout', methods=['POST'])
def signout():
    data = request.json
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    if user:
        est_timezone = pytz.timezone('America/New_York')
        current_time_est = datetime.now(tz=est_timezone)
        log_entry = LibraryLog.query.filter_by(user_id=user_id, time_out=None).first()
        if log_entry:
            log_entry.time_out = current_time_est
            db.session.commit()
            socketio.emit('refresh', namespace='/library')
            return jsonify(message=f"{user.name} signed out successfully."), 200
        else:
            return jsonify(error="User is not currently signed in."), 400
    else:
        return jsonify(error="User not found."), 404
    
    
@app.route('/set_max_capacity', methods=['GET', 'POST'])
def set_max_capacity():
    if request.method == 'POST':
        max_capacity = request.json.get('maxCapacity')
        # Update the maximum capacity (store it in a variable, database, etc.)
        print('New Maximum Capacity:', max_capacity)
        # Return a JSON response indicating success
        return jsonify({'message': 'Maximum capacity set successfully'})


@app.route('/library_action', methods=['POST'])
def library_action():
    data = request.form
    user_id = data.get('user_id')
    now = time.time()
    user = User.query.get(user_id)
    if user:
        # Check if the user is currently signed in
        log_entry = LibraryLog.query.filter_by(user_id=user_id, time_out=None).first()

        if log_entry:
            # If signed in, sign them out
            log_entry.time_out = datetime.utcnow()
            db.session.commit()
            message = f"{user.name} signed out successfully."
        else:
            # If not signed in, sign them in
            log_entry = LibraryLog(user_id=user_id)
            db.session.add(log_entry)
            db.session.commit()
            message = f"{user.name} signed in successfully."

        # Recalculate the count of currently signed-in students
        signed_in_count = LibraryLog.query.filter(LibraryLog.time_out.is_(None)).count()

        library_logs = LibraryLog.query.all()

        socketio.emit('refresh', namespace='/library')
        return render_template('library_view.html', library_logs=library_logs, message=message, signed_in_count=signed_in_count), 200
    else:
        return jsonify(error="User not found."), 404

# Endpoint for viewing library database
@app.route('/library_view')
def library_view():
    library_logs = LibraryLog.query.all()
    signed_in_count = LibraryLog.query.filter(LibraryLog.time_out.is_(None)).count()
    return render_template('library_view.html', library_logs=library_logs, signed_in_count=signed_in_count)

@socketio.on('connect', namespace='/library')
def test_connect():
    print('Client connected')


if __name__ == '__main__':
    with app.app_context():
        load_student_data()

    app.run(debug=True, host = '0.0.0.0', port = 5000)
