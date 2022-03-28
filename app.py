import os
import pathlib

import requests
from flask import Flask, session, abort, redirect, request, render_template, url_for
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import mysql.connector

from functools import wraps

from coolname import generate_slug
import pandas as pd

app = Flask("Google Login App")
app.secret_key = "Quizzy"


con = mysql.connector.connect(
  host="localhost",
  user="root",
  password="root",
  database="quizzy"
)

cursor = con.cursor()

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

    # con = mysql.connector.connect(host='localhost', user='root', password='root')
    # cursor = con.cursor()
    # con.commit()

    # cursor.execute("CREATE DATABASE IF NOT EXISTS quizzy;")
    # cursor.execute("USE quizzy;")
    
    
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
    return "Click here to Login <a href='/login'><button>Login</button></a>"


@app.route("/landing_page")
@login_is_required
def landing_page():
    return f"Hello {session['name']}! <br/> <a href='/landing_page/create_quiz'><button>Create Quiz</button></a> <br/> <a href='/landing_page/take_quiz'><button>Take Quiz</button></a> <br/> <a href='/logout'><button>Logout</button></a>"


# Upload folder
UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER


def parseCSV(filePath, quiz_id):

    # CSV Column Names
    col_names = ['q_desc','option_one','option_two', 'option_three', 'option_four' , 'correct_option', 'q_marks']
    
    # Use Pandas to parse the CSV file
    csvData = pd.read_csv(filePath,names=col_names, header=None)


    # create the questions table
    cursor.execute("CREATE TABLE IF NOT EXISTS QUESTIONS (quiz_id varchar(100) NOT NULL, q_desc varchar(100) NOT NULL, option_one varchar(100) NOT NULL, option_two varchar(100) NOT NULL, option_three varchar(100) NOT NULL, option_four varchar(100) NOT NULL, correct_option varchar(100) NOT NULL, q_marks int(100) NOT NULL, CONSTRAINT fk_questions FOREIGN KEY (quiz_id) REFERENCES QUIZ(quiz_id) ON DELETE CASCADE ON UPDATE CASCADE);")

    # Loop through the Rows
    total_marks = 0
    for i,row in csvData.iterrows():
        total_marks += row['q_marks']
        sql = "INSERT INTO questions (quiz_id, q_desc, option_one, option_two, option_three, option_four, correct_option, q_marks) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        value = (quiz_id, row['q_desc'],row['option_one'],row['option_two'],row['option_three'],row['option_four'],row['correct_option'], row['q_marks'])
        cursor.execute(sql, value)
        con.commit()

    cursor.execute("UPDATE QUIZ SET total_marks = %s where quiz_id = %s;", (total_marks, quiz_id))
    con.commit()

@app.route("/landing_page/create_quiz")
@login_is_required
def create_quiz():
    return render_template('create_quiz.html')

# Get the uploaded files
@app.route("/landing_page/create_quiz", methods=['POST'])
def createQuiz():
    
    # create unique quiz details
    quiz_id = generate_slug(2)
    quiz_name = request.form.get('q_name')
    
    # Add to database

    # Create Quiz table
    cursor.execute("CREATE TABLE IF NOT EXISTS QUIZ(quiz_id varchar(100) NOT NULL PRIMARY KEY, quiz_name varchar(100) NOT NULL, total_marks int(100));")
    con.commit()

    # enter quiz details into the db
    cursor.execute("INSERT INTO QUIZ(quiz_id, quiz_name) VALUES (%s, %s);", (quiz_id, quiz_name))
    con.commit()
    
    # get the uploaded file
    uploaded_file = request.files['file']
    
    if uploaded_file.filename != '':
        # set the file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
        
        # save the file
        uploaded_file.save(file_path)
         
        parseCSV(file_path, quiz_id)
      
    return "<p>Your quiz {:s} is created and unique test ID is {:s}</p>".format(quiz_name, quiz_id)
    

entered_answers = []

@app.route("/landing_page/take_quiz", methods=['GET','POST'])
@login_is_required
def take_quiz():
    global entered_answers
    if request.method == 'POST':
        received_id  = request.form.get('q_id')
        # print(received_id)
        return redirect(url_for('new_route', received_id=received_id))

    return render_template('take_quiz.html')

@app.route('/landing_page/take_quiz/<string:received_id>', methods=['GET','POST'])
def new_route(received_id):
      
    cursor.execute("SELECT * from QUESTIONS where quiz_id = %s",(received_id,))
    rows = cursor.fetchall()

    if request.method == 'POST':
        for i in range(len(rows)):
            answer = request.form.get(str(i))
            entered_answers.append(answer)
        # print(entered_answers)
        return redirect(url_for('view_score', received_id=received_id))

    return render_template('questions.html', rows = rows, length = len(rows))

@app.route('/viewscore/<string:received_id>', methods=['GET','POST'])
def view_score(received_id):
    cursor.execute("SELECT correct_option from QUESTIONS where quiz_id = %s",(received_id,))
    answers = cursor.fetchall()

    cursor.execute("SELECT q_marks from QUESTIONS where quiz_id = %s",(received_id,))
    marks = cursor.fetchall()      
      
    score = 0
    for i in range(len(answers)):
        if answers[i][0] == entered_answers[i]:
            score += marks[i][0]
    # print(len(answers))
    # print(marks)
    # print(answers)
    # print(entered_answers)
    return "Your score is: {:d}".format(score)



if __name__ == "__main__":
    app.run(debug=True)