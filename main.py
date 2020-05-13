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
cel = Celery('latex', broker='redis://localhost')

def confirmation(data):
    return config.confirmation_string

def default_data_handler(data):
    app.logger.warn('Unknown type received: '+repr(data))

def slash_help(*args, user_id=None):
    opt_man = data_managers.UserOptsManager(vkapi)
    cic = opt_man.get_code_in_caption(user_id)
    tic = opt_man.get_time_in_caption(user_id)
    dpi = opt_man.get_dpi(user_id)
    output = f'''Command list, values in <brackets> are required parameters:
/help -- this help

Preamble commands:
/reset-preamble -- restore your custom preamble to the default -- use this if you get render errors on valid code
/show-preamble -- show your custom preamble
/add-preamble <line> -- add a line to the end of your custom preamble
/delete-preamble <line-index> -- remove a line by its index from your custom preamble

Settings commands (current settings are in <brackets>):
/set-caption-code <{1 if cic else 0}> -- do you want to have LaTeX code in the message caption?
/set-render-time <{1 if tic else 0}> -- do you want render time in the message caption?
/set-dpi <{dpi}> -- set image resolution, higher is better
'''

    return output

def reset_preamble(*args, user_id=None):
    preamb_man = data_managers.PreambleManager(vkapi)
    preamb_man.set_list(user_id, preamb_man.default_preamble)
    return 'Your custom preamble has been reset.'

def set_caption_code(val, user_id=None):
    if val not in list('01'):
        return 'Please provide a (0 for no) or (1 for yes) as parameter.'
    opt_man = data_managers.UserOptsManager(vkapi)
    opt_man.set_code_in_caption(user_id, val=='1')
    return 'The next renders made for you will ' + ('not ' if val=='0' else "") + 'have their code as part of the image caption.'

def set_dpi(val, user_id=None):
    try:
        val = int(val)
        if val not in range(20, 4001):raise ValueError
    except ValueError:
        return 'Please provide an integer in the range (20, 4000).'

    opt_man = data_managers.UserOptsManager(vkapi)
    opt_man.set_dpi(user_id, val)

def show_preamble(user_id=None):
    preamb_man = data_managers.PreambleManager(vkapi)
    outp = 'Your preamble:\n\n'
    for ind, val in enumerate(preamb_man.strip_empty(preamb_man.get_as_list(user_id))):
        outp += f'{ind}. {val}\n'
    if ind==0: # wrote only one line
        outp+='\nYour custom preamble only contains one line. If you delete it, your preamble will be reset to the default.'

    return outp

def add_preamble(*args, user_id=None):
    line = ' '.join(args)
    preamb_man = data_managers.PreambleManager(vkapi)
    try:
        preamble = preamb_man.strip_empty(preamb_man.get_as_list(user_id))
        preamble.append(line)
        preamb_man.set_list(user_id, preamble)
        return f'Added "{line}" to your preamble as line number {len(preamble)-1}.'
    except ValueError as e:
        return ' '.join(e.args)

def delete_preamble(ind, user_id=None):
    try:
        ind = int(ind)
    except ValueError:
        return 'The line index must be an integer.'
    preamb_man = data_managers.PreambleManager(vkapi)
    preamble = preamb_man.strip_empty(preamb_man.get_as_list(user_id))
    try:
        rem_line = preamble.pop(ind)
        preamb_man.set_list(user_id, preamble)
        return f'Line with index {ind} was removed. It was: "{rem_line}"'
    except IndexError:
        return f'There is no line with index {ind}, check /show-preamble'

def set_caption_time(val, user_id=None):
    if val not in list('01'):
        return 'Please provide a (0 for no) or (1 for yes) as parameter.'
    opt_man = data_managers.UserOptsManager(vkapi)
    opt_man.set_time_in_caption(user_id, val=='1')
    return 'The next renders made for you will ' + ('not ' if val=='0' else "") + 'have the render time as part of the image caption.'



slash_commands = {
    'help': slash_help,
    'reset-preamble': reset_preamble,
    'set-caption-code': set_caption_code,
    'set-dpi': set_dpi,
    'show-preamble': show_preamble,
    'add-preamble': add_preamble,
    'delete-preamble': delete_preamble,
    'set-render-time': set_caption_time,
    }

def recv_message(data):
    message = data['object']['message']
    sender = message['from_id']
    reply_to = message['peer_id']
    
    def reply(t):
        vkapi.messages.send(peer_id=reply_to, message=(f'@id{sender}: ' if sender!=reply_to else '')+t, random_id=0)
    
    try:
        text = message['text']
        if not text: raise KeyError
    except KeyError:
        reply('Your message did not contain text, but it is required.')
        return

    grp_ref = re.search('\\[.*\\|.*\\] ', text)
    if grp_ref != None:
        text = text[(grp_ref.span()[1]):]

    if text.startswith('/'):
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

    RATE_LIM_INTERVAL = 30
    opt_man = data_managers.UserOptsManager(vkapi)
    if time.time() - opt_man.get_last_render_time(sender) < RATE_LIM_INTERVAL: # unregistered rate-limiting
        reply(f'It\'s been only {time.time() - opt_man.get_last_render_time(sender)}, please wait at least {RATE_LIM_INTERVAL} seconds before requesting next render')
        return

    workers = cel.control.inspect(timeout=0.2).ping()
    if workers is None:
        reply('''ERROR: No Celery workers responded to ping!
This is a serious problem!

The bot is currently unable to render images.
Please contact this bot's admin and inform them of this issue.''')
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

