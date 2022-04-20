# Quizzy

A MCQ quiz platform where the quiz creator can create a quiz with n-number of questions, add options, select the correct option and add marks per question. Finish the creation of a quiz and get a quiz code generated. Circulate the code with your test takers. Test takers enter the quiz code/link and take the quiz. Submit the quiz and get your scores.


### Installation

```bash
pip install -r requirements.txt
```

### Usage

Create a database locally, open app.py and setup the database connection
```python
host="hostname",
user="username",
password="password",
database="db_name"
```

Create your Google OAuth Credentials and add the client_secret.json file to the root directory


Run the program using 
```bash
python app.py or flask run
```

### Quiz Codes for Created Quizzes
1. copper-serval
