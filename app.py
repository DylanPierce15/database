# Sign everyone out after lunch
#add a token so only librarian can access the web

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from flask_socketio import SocketIO
import time
from datetime import datetime, timezone, timedelta
import pytz
from pytz import timezone
from functools import wraps

data_hashmap = {}


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students_library.db'
LIBRARIAN_TOKEN = 'a'
db = SQLAlchemy(app)
socketio = SocketIO(app)



def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    print("Value:", value)
    print("Type of Value:", type(value))
    
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    
    print("Value after conversion (if applicable):", value)
    
    if isinstance(value, datetime):
        value_utc = value.replace(tzinfo=pytz.utc)
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

        if data.empty:
            print("Error: CSV file is empty.")
            return
        if not data.columns.any():
            print("Error: CSV file does not have columns.")
            return

        print("Loaded Data:")

        for _, row in data.iterrows():
            if 'id_code' in row:
                name = row['name']
                id_code = str(row['id_code'])
                data_hashmap[name] = id_code

                user_exists = User.query.filter_by(id=id_code).first()
                if not user_exists:
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

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = 'a'
        print(f"Received Token: {token}")  # Debug statement
        if not token or token != LIBRARIAN_TOKEN:
            print("Token is missing or invalid!")  # Debug statement
            return jsonify({'message': 'Token is missing or invalid!'}), 403
        return f(*args, **kwargs)
    return decorated_function

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
        current_time_utc = datetime.now(timezone.utc)
        current_time_adjusted = current_time_utc - timedelta(hours = 4)
        log_entry = LibraryLog.query.filter_by(user_id=user_id, time_out=None).first()
        if log_entry:
            log_entry.time_out = current_time_adjusted
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
        current_time_utc = datetime.now(pytz.utc)
        current_time_adjusted = current_time_utc - timedelta(hours = 4)
        if log_entry:
            # If signed in, sign them out
            log_entry.time_out = current_time_adjusted
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
@token_required
def library_view():
    # Get query parameters for date and name filtering
    date_filter = request.args.get('date')
    name_filter = request.args.get('name')
    show_all = request.args.get('show_all')

    # Get library logs based on date and name filters
    if show_all:
        library_logs = LibraryLog.query
    else:
        if date_filter:
            try:
                date_filter_dt = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                return jsonify(error="Invalid date format. Please use YYYY-MM-DD."), 400
        else:
            # Default to today's date if no date is provided
            date_filter_dt = datetime.now().date()
        
        # Filter logs for the specific date
        library_logs = LibraryLog.query.filter(
            LibraryLog.time_in >= date_filter_dt,
            LibraryLog.time_in < date_filter_dt + timedelta(days=1)
        )

    if name_filter:
        library_logs = library_logs.join(User).filter(User.name == name_filter)

    library_logs = library_logs.all()

    # Count the number of students currently signed in
    signed_in_count = LibraryLog.query.filter(LibraryLog.time_out.is_(None)).count()

    return render_template('library_view.html', library_logs=library_logs, signed_in_count=signed_in_count)



if __name__ == '__main__':
    with app.app_context():
        load_student_data()

    app.run(debug=True, host = '0.0.0.0', port = 5000)
