import config
from peewee import *
from flask import Flask, request
import re
from latex_celery_tasks import *
import traceback

database = MySQLDatabase('inlatex', user='inlatex', password='inlatex')

app = Flask(__name__)

celery = Celery('latex', broker='redis://localhost')

def confirmation(data):
    return config.confirmation_string

def default_data_handler(data):
    app.logger.warn('Unknown type received: '+repr(data))

def recv_message(data):
    message = data['object']['message']
    sender = message['from_id']
    reply_to = message['peer_id']
    text = message['text']
    grp_ref = re.search('\\[.*\\|.*\\] ', text)
    if grp_ref != None:
        text = text[(grp_ref.span()[1]):]
    if sender == reply_to:
        render_for_user.apply_async((sender, text))
    else:
        render_for_groupchat.apply_async((sender, reply_to, text))

type_map = {
'confirmation': confirmation,
'message_new': recv_message,
}


@app.errorhandler(Exception)
def error(error):
    traceback.print_exc()
    return 'ok'

@app.route('/')
def index():
    return 'Hello LaTeX!'

@app.route('/api', methods=['POST'])
def api():
    data = request.get_json(force=True)
    type = data['type']
    fun = type_map.get(type, default_data_handler)
    res = fun(data)
    if res is None:
        return 'ok'
    else:
        return res

