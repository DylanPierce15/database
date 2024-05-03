import requests

# Define the URL of the Flask application's /library_action route
url = 'http://10.56.52.148:5000/library_action'

# Define the user ID you want to send
user_id = '10022'

# Create a dictionary with the user ID
data = {'user_id': user_id}

# Send an HTTP POST request to the URL with the user ID data
response = requests.post(url, data=data)

# Check the status code of the response
if response.status_code == 200:
    print('Code sent successfully.')
else:
    print(f'Failed to send code. Status code: {response.status_code}')
