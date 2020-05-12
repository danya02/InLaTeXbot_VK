import config
from flask import Flask, request
import re
import vk_api
from latex_celery_tasks import *
import traceback
import data_managers

app = Flask(__name__)
vk_session = vk_api.VkApi(token=config.access_token)
vkapi = vk_session.get_api()
celery = Celery('latex', broker='redis://localhost')

def confirmation(data):
    return config.confirmation_string

def default_data_handler(data):
    app.logger.warn('Unknown type received: '+repr(data))

def slash_help(**kwargs):
    return '''Command list:
/help -- this help
/reset-preamble -- restore your saved preamble to the default
'''

def reset_preamble(*args, user_id=None):
    preamb_man = data_managers.PreambleManager(vkapi)
    preamb_man.set_list(user_id, preamb_man.default_preamble)
    return 'Your custom preamble has been reset.'


slash_commands = {
    'help': slash_help,
    'reset-preamble': reset_preamble
    }

def recv_message(data):
    message = data['object']['message']
    sender = message['from_id']
    reply_to = message['peer_id']
    text = message['text']

    def reply(t):
        vkapi.messages.send(peer_id=reply_to, message=t, random_id=0)

    grp_ref = re.search('\\[.*\\|.*\\] ', text)
    if grp_ref != None:
        text = text[(grp_ref.span()[1]):]

    if sender==reply_to and text.startswith('/'):
        command = text[1:].split()
        if command[0] in slash_commands:
            fun = slash_commands[command[0]]
            try:
                answer = fun(*(command [1:]), user_id=sender)
            except TypeError:
                reply('Wrong number of arguments for command, for command list type "/help".')
            except:
                reply('ERROR\n'+traceback.format_exc())
            else:
                if answer:
                    reply(answer)
        else:
            reply(f'Unknown command "{command[0]}", for list type "/help".')
        return

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

