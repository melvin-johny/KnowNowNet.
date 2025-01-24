from flask import Flask, render_template, request, redirect, url_for, session
from flask import request
from flask_mysqldb import MySQL
from datetime import datetime
import hashlib
import wikipediaapi
import requests
from flask import jsonify
from bs4 import BeautifulSoup
import bcrypt




# Flask app setup
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# MySQL configurations
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'  # MySQL username
app.config['MYSQL_PASSWORD'] = '626858'   # No password
app.config['MYSQL_DB'] = 'chatbot'  # Name of your database

mysql = MySQL(app)




# Define functions for chatbot logic

def get_wikipedia_data(topic, language='en', num_sentences=2):
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    headers = {'User-Agent': user_agent}

    try:
        wiki_wiki = wikipediaapi.Wikipedia(language, headers=headers)
        page_py = wiki_wiki.page(topic)

        if not page_py.exists():
            print(f"Page '{topic}' does not exist on Wikipedia.")
            return None

        print("Title:", page_py.title)
        summary_sentences = page_py.summary.split('. ')[:num_sentences]
        return f"{page_py.title}: {'.'.join(summary_sentences)}"
    except Exception as e:
        print(f"Error fetching data from Wikipedia API: {e}")
        return None

def google_search_query(query):
    try:
        googlesearch = query.lower()
        url = f"https://google.com/search?q={googlesearch}"
        request_results = requests.get(url)
        soup = BeautifulSoup(request_results.text, "html.parser")
        result_div = soup.find("div", class_="BNeawe")
        if result_div:
            result = result_div.text
            if result.endswith("- Wikipedia"):
                term = result.split("- Wikipedia")[0].strip()
                wikipedia_result = get_wikipedia_data(term)
                if wikipedia_result:
                    return wikipedia_result
                else:
                    return "Sorry, I cannot think of a reply for that."
            else:
                return result
        else:
            return None
    except Exception as e:
        print("An error occurred during Google search:", e)
        return None

def chatbot_query(query):
    fallback = 'Sorry, I cannot think of a reply for that.'

    # Try Wikipedia first
    wikipedia_reply = get_wikipedia_data(query)
    if wikipedia_reply:
        return wikipedia_reply

    # If Wikipedia doesn't have the answer, fallback to Google search
    google_search_reply = google_search_query(query)
    if google_search_reply:
        return google_search_reply

    # If both fail, return fallback message
    return fallback




# Middlewares

def check_logged_in():
    if 'user' in session:
        # User is logged in, redirect to home page
        return redirect(url_for('chat'))
    else:
        # User is not logged in
        return None
    

def save_chat_to_database(user_id, message, reply):
    try:
        cur = mysql.connection.cursor()
        sql = "INSERT INTO chat_history (user_id, message, reply) VALUES (%s, %s, %s)"
        values = (user_id, message, reply)
        cur.execute(sql, values)
        mysql.connection.commit()  # Commit the changes to the database
        cur.close()
    except Exception as e:
        print("Error occurred while saving to database:", e)
        mysql.connection.rollback()  


def get_chat_history(user_id):
    try:
        cur = mysql.connection.cursor()
        sql = "SELECT id, message, reply, timestamp FROM chat_history WHERE user_id = %s"
        cur.execute(sql, (user_id,))
        chat_history = cur.fetchall()
        cur.close()
        # Restructure the data into a list of dictionaries
        chat_history_with_info = []
        for row in chat_history:
            message_info = {
                "id": row[0],
                "user_id": user_id,
                "message": row[1],
                "reply": row[2],
                "timestamp": row[3].strftime("%d-%m-%Y %I:%M:%S %p")
            }
            chat_history_with_info.append(message_info)
        return chat_history_with_info
    except Exception as e:
        print("Error occurred while fetching chat history:", e)
        return []

# Middlewares
    


@app.route("/", methods=["GET", "POST"])
def chat():
    # Check if user is logged in
    if 'user' in session:
        if request.method == "GET":
            user_id = session['user']['id']
            user_name = session['user']['name']
            chat_history = get_chat_history(user_id)
            print(chat_history)
            return render_template("index.html", user_name=user_name, chat_history=chat_history)
        else:
            query = request.form.get("message")
            if query:
                reply = chatbot_query(query)
                user_id = session['user']['id']
                save_chat_to_database(user_id, query, reply)
                return reply
            else:
                return render_template("index.html")
    else:
        # User is not logged in, redirect to login page
        return redirect(url_for('login'))
        

# Authentication routes
@app.route('/register', methods=['GET', 'POST'])
def register():

    redirect_page = check_logged_in()
    if redirect_page:
        return redirect_page
    if request.method == 'POST':
        return handle_registration_form()
    else:
        return render_template('register.html')

def handle_registration_form():
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    # Check if email already exists
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    existing_user = cur.fetchone()
    cur.close()

    if existing_user:
        error_message = 'Email already exists. Please choose a different email.'
        return render_template('register.html', error=error_message)

    # Check if passwords match
    if password != confirm_password:
        error_message = 'Passwords do not match. Please try again.'
        return render_template('register.html', error=error_message)

    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert data into the database
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
    mysql.connection.commit()
    cur.close()

    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    redirect_page = check_logged_in()
    if redirect_page:
        return redirect_page
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Fetch user from the database based on email
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user:
            # Extract the hashed password from the tuple
            print(user)
            hashed_password = user[3]  # Assuming the password field is at index 3

            # Check if the entered password matches the hashed password using bcrypt
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                # Passwords match, redirect to home page
                session['user'] = {
                    'id': user[0],         # Assuming user ID is at index 0
                    'name': user[1],       # Assuming user name is at index 1
                    'email': user[2],      # Assuming user email is at index 2
                }
                return redirect(url_for('chat'))
            else:
                # Passwords do not match, show error
                error_message = 'Incorrect email or password. Please try again.'
                return render_template('login.html', error=error_message)
        else:
            # User with the entered email not found, show error
            error_message = 'User not found. Please register.'
            return render_template('login.html', error=error_message)
    else:
        # GET request, render the login form
        return render_template('login.html')
    

@app.route('/logout')
def logout():
    # Clear the user session
    session.pop('user', None)
    # Redirect to the login page
    return redirect(url_for('login'))



@app.route('/clear_chat_history', methods=['POST'])
def clear_chat_history():
    # Retrieve user_id from session
    user_id = session['user']['id']
    
    # Execute SQL query to delete records with matching user_id
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM chat_history WHERE user_id = %s", (user_id,))
    mysql.connection.commit()  # Commit the transaction
    cur.close()

    return redirect(url_for('chat'))
    
    

if __name__ == '__main__':
    app.run(debug=True)
