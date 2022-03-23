import os
import pathlib

import requests
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import mysql.connector

from functools import wraps

app = Flask("Google Login App")
app.secret_key = "CodeSpecialist.com"

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "80687604948-vvo4h9b9ocbk3aso2o1fg5qil9hm2ept.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


# def login_is_required(function):
#     def wrapper(*args, **kwargs):
#         if "google_id" not in session:
#             return abort(401)  # Authorization required
#         else:
#             return function()

#     return wrapper

def login_is_required(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if 'loggedin' in session:
			return f(*args, **kwargs)
		else:
			return abort(401)
	return wrap


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    con = mysql.connector.connect(host='localhost', user='root', password='root')
    cursor = con.cursor()
    con.commit()

    cursor.execute("CREATE DATABASE IF NOT EXISTS quizzy;")
    cursor.execute("USE quizzy;")
    
    
    cursor.execute("CREATE TABLE IF NOT EXISTS users(UserID int(50) AUTO_INCREMENT, Name varchar(50) NOT NULL, Email varchar(100) NOT NULL, PRIMARY KEY (UserId));")
    con.commit()

    # Adding an initial entry
    # cursor.execute("INSERT INTO users VALUES (1, 'Test Name', 'TestEmail@email.com');")
    # con.commit()

    
    cursor.execute("SELECT * FROM users WHERE Email = %s AND Name = %s;", (id_info.get("email"), id_info.get("name"), ))
    account = cursor.fetchone()

    if not account:
        cursor.execute("INSERT INTO users (Name, Email) VALUES (%s, %s);", (id_info.get("name"), id_info.get("email")))
        con.commit()

    session['loggedin'] = True
    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")


    return redirect("/landing_page")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/")
def index():
    return "Hello World <a href='/login'><button>Login</button></a>"


@app.route("/landing_page")
@login_is_required
def landing_page():
    return f"Hello {session['name']}! <br/> <a href='/landing_page/create_quiz'><button>Create Quiz</button></a> <br/> <a href='/landing_page/take_quiz'><button>Take Quiz</button></a> <br/> <a href='/logout'><button>Logout</button></a>"


# Upload folder
UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER


@app.route("/landing_page/create_quiz")
@login_is_required
def create_quiz():
    return render_template('questions.html')

# Get the uploaded files
@app.route("/landing_page/create_quiz", methods=['POST'])
def createQuiz():
      # get the uploaded file
      quiz_name = request.form.get('q_name')
      uploaded_file = request.files['file']
      if uploaded_file.filename != '':
           file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
          # set the file path
           uploaded_file.save(file_path)
          # save the file
      return "<p>Your quiz {:s}  is created</p>".format(quiz_name)


@app.route("/landing_page/take_quiz")
@login_is_required
def take_quiz():
    return "You can take quizzes here"


if __name__ == "__main__":
    app.run(debug=True)