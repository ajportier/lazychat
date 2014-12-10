#!/usr/bin/env python
from flask import (Flask, jsonify, request, g, render_template)
from flask.ext.mongoengine import MongoEngine
from flask.ext.httpauth import HTTPBasicAuth
from mongoengine.queryset import DoesNotExist
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer
        as Serializer, BadSignature, SignatureExpired)
from datetime import datetime, timedelta

##### Config #####
app = Flask(__name__)
app.config["SECRET_KEY"] = "secretKey"
app.config["MONGODB_SETTINGS"] = {
        'db':'lazychat',
        'host':'mongo',
        'port': 27017,
        }

db = MongoEngine(app)
auth = HTTPBasicAuth()

# create one "epoch" datetime object for conversion later
epoch = datetime.fromtimestamp(float(0))

##### Models #####
class Chat(db.Document):
    created = db.DateTimeField(default=datetime.now, required=True)
    username = db.StringField(max_length=255, required=True)
    content = db.StringField(required=True)
    private_user = db.StringField(required=False)

    def __unicode__(self):
        return str(self.username) + "@" + str(self.created)

    meta = {
        'indexes': ['-created'],
        'ordering': ['-created'],
    }

class User(db.Document):
    username = db.StringField(max_length=255, required=True)
    password_hash = db.StringField(required=False)
    last_seen = db.DateTimeField(required=False)

    def __unicode__(self):
        return str(self.username)

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=3600):
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'username': self.username})

    # This is static so we can get a "user" object back from a token
    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token
        user = User.objects.get(username=data['username'])
        return user

    meta = {
        'indexes': ['username'],
    }

##### Views #####
@app.route('/')
def index_page():
    return render_template('index.html')

# Sets up user password verification method
@auth.verify_password
def verify_password(username_or_token, password):
    user = User.verify_auth_token(username_or_token)
    if not user:
        try:
            user = User.objects.get(username = username_or_token)
            if not user.verify_password(password):
                return False
        except DoesNotExist:
            return False
    g.user = user
    return True


# Logs in user and returns a token valid for a certain duration
@app.route('/user/login', methods=['GET'])
@auth.login_required
def login_user():
    token = g.user.generate_auth_token(3600)
    return jsonify({'token': token.decode('ascii'), 'duration':3600})


@app.route('/user/register', methods=['POST'])
def add_user():
    if not request.json:
        return (jsonify({'error':'Request not JSON'}),400)
    try:
        username = request.json['username']
        password = request.json['password']
    except KeyError as e:
        return(jsonify({'error':'Missing key {}'.format(e)}),400)
    try:
        user = User.objects.get(username=username)
        return(jsonify({'error':'User {} already exists'.format(username)}),400)
    except DoesNotExist:
        user = User(username=username)
        user.hash_password(password)
        user.save()
        return (jsonify({'response':'OK'}),201)


@app.route('/user/list_current', methods=['GET'])
@auth.login_required
def get_current_users():

    # create a timestamp for "delta" seconds ago
    delta = 10
    td = datetime.now() - timedelta(seconds=delta)

    # return all users seen within the last "delta" seconds
    response = {}
    users = User.objects.filter(last_seen__gt=td)
    for user in users:
        response.update({str(user):
                {
                    'username':user.username,
                    'last_seen':user.last_seen,
                }
            })
    return (jsonify(response),200)
   

@app.route('/chat/add', methods=['POST'])
@auth.login_required
def add_chat():
    if not request.json:
        return(jsonify({'error':'Request not JSON'}),400)
    try:
        username = str(g.user)
        content = request.json['content']
        chat = Chat(username=username, content=content)
        chat.save()
    except KeyError as e:
        return(jsonify({'error':'Missing key {}'.format(e)}),400)

    # if this is a targeted chat, update the document and save again
    try:
        private_user = request.json['private_user']
        p_user = User.objects.get(username=private_user)
        chat.private_user = private_user
        chat.save()
    except KeyError:
        # If no "private_user" value is set, move on
        pass
    except DoesNotExist:
        # Refuse to create private chats for users not registered
        return(jsonify({'error':'No such user by that name'}),400)

    # If you make it here, return a 201 "created" status and OK
    return (jsonify({'response':'OK'}),201)


@app.route('/chat/get', methods=['POST'])
@auth.login_required
def get_chats():
    if not request.json:
        return (jsonify({'error':'Request not JSON'}),400)

    # every time the user checks in, update the "last_seen" timestamp
    g.user.last_seen = datetime.now
    g.user.save()

    try:
        # take the "start_time" value from the JSON object and make it datetime
        timestamp = request.json['start_time']
        start_time = datetime.fromtimestamp(float(timestamp) + 1)

        # query Mongo for chats newer than start_time (i.e since last checked)
        chats = Chat.objects.filter(created__gt=start_time)
        response = {}
        for chat in chats:
            chat_contents = {}
            try:
                # If the chat contains a private_user, make sure this user can
                # see it, and if they can supply that information with the chat
                if chat.private_user:
                    assert (chat.private_user == str(g.user)) or \
                            chat.username == str(g.user)
                    chat_contents.update({'private_user':chat.private_user})

                # convert the datetime object into epoch time
                epoch_time = int((chat.created - epoch).total_seconds())

                # add the chat response with the epoch timestamp
                chat_contents.update(
                    {
                        'created':epoch_time,
                        'username':chat.username,
                        'content':chat.content
                    })
                response.update({str(chat):chat_contents})
            except AssertionError:
                # If any of the assertion tests fail, move on
                pass
        return (jsonify(response),200)
    except KeyError as e:
        return(jsonify({'error':'Missing key {}'.format(e)}),400)

# The following method is for testing purposes only
@app.route('/chat/nuke', methods=['GET'])
def nuke_chats():
    chats = Chat.objects.all()
    for chat in chats:
        chat.delete()
    return (jsonify({'response':'OK'}),200)


if __name__ == '__main__':
    app.run(debug=True)
