import config
import flask
from flask import Flask, request, url_for, render_template
from werkzeug.exceptions import HTTPException
import re
import vk_api
import latex_celery_tasks
import traceback
import data_managers
import json
import stats
import utils
import time
import random
from idempotency import is_unique_event

app = Flask(__name__)
#app.config['SERVER_NAME'] = 'https://inlatex.danya02.ru'
vk_session = vk_api.VkApi(token=config.access_token)
vkapi = vk_session.get_api()
utils = utils.VKUtilities(vkapi)
cel = latex_celery_tasks.Celery('latex', broker='redis://localhost')

def ERROR(trace, user_id=None, text=None):
    uid = stats.record_error(trace, user_id, text)
    url = url_for('error_view', uid=uid, _external=True)
    vkapi.messages.send(peer_id=config.owner_id, message='Unknown error encountered! Details at '+url, random_id=0)
    return url 

@app.errorhandler(Exception)
def error(error):
    # pass through HTTP errors
    if isinstance(error, HTTPException):
        return error
    traceback.print_exc()
    ERROR(traceback.format_exc(), None, None)
    return 'ok'


@app.route('/view-error/<uid>')
def error_view(uid):
    try:
        err = stats.get_error(uid)
        return render_template('error-report.html', err=err)
    except stats.Error.DoesNotExist:
        return 'no such error', 404
    except:
        return traceback.format_exc()

def confirmation(data):
    return config.confirmation_string

def default_data_handler(data):
    app.logger.warn('Unknown type received: '+repr(data))

def slash_help(*args, user_id=None):
    opt_man = data_managers.UserOptsManager(vkapi)
    cic = opt_man.get_code_in_caption(user_id)
    tic = opt_man.get_time_in_caption(user_id)
    dpi = opt_man.get_dpi(user_id)
    output = f'''Command list, values in <brackets> are required parameters, in [brackets] are optional:
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

    is_manager = data_managers.ManagerStore(vkapi)
    if is_manager[user_id]:
        output += f'''

As a manager, you also have these commands:

/ratelimit <@-user> -- enable rate-limiting for this user
/unratelimit <@-user> -- disable rate-limiting for this user
/getratelimit <@-user> -- check the state of rate-limiting for this user
/top-by-time [how-many]-- get top users by time taken to render
/top-by-renders [how-many] -- get top users by render requests
/top-by-errors [how-many] -- get top users by errors during rendering
/error-out -- intentionally cause an exception to test the error reporting feature
'''
    if user_id==config.owner_id:
        output += f'''

As the bot owner, you also have these commands:
/promote <@-user> -- make user a manager
/demote <@-user> -- stop user being a manager
/get-promoted <@-user> -- check whether this user is a manager
/delete-error <uuid> -- delete an error report by its uuid
/delete-all-errors -- delete all error reports
/show-errors [how-many] -- show a list of error reports
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
    rlstore = data_managers.DisabledRateLimitStore(vkapi)
    max_dpi = 1200 if not rlstore[user_id] else 10000
    try:
        val = int(val)
        if val not in range(20, max_dpi):raise ValueError
    except ValueError:
        return f'Please provide an integer in the range (20, {max_dpi}). The default value is 300.'

    opt_man = data_managers.UserOptsManager(vkapi)
    opt_man.set_dpi(user_id, val)
    return f'Your DPI has been updated to {val}'

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

def requires_owner(func):
    def wrapper(*args, user_id=None):
        if user_id != config.owner_id:
            return 'This command is only available to the bot admin'
        return func(*args)
    return wrapper

def requires_manager(func):
    def wrapper(*args, user_id=None):
        is_manager = data_managers.ManagerStore(vkapi)
        if is_manager[user_id]:
            return func(*args)
        else: 
            return 'This command is only available to managers. Contact the bot\'s admin to become one.'
    return wrapper

def resolves_userspec(func):
    def wrapper(userspec):
        try:
            resolved = utils.resolve_to_user_id(userspec)
        except:
            return 'Failed while resolving userspec, see '+ERROR(traceback.format_exc(), None, userspec)
        return func(resolved)
    return wrapper

@requires_manager
@resolves_userspec
def unratelimit(user_id):
    rlstore = data_managers.DisabledRateLimitStore(vkapi)
    rlstore[user_id] = True
    err = ''
    try:
        vkapi.messages.send(user_id=user_id, message='Your rate-limit has been removed.', random_id=0)
    except:
        err = 'But I can\'t send them messages, they may have blocked them or not started a chat with the bot.'
    return f'Disabled ratelimiting for user id {user_id}. {err}'

@requires_manager
@resolves_userspec
def ratelimit(user_id):
    rlstore = data_managers.DisabledRateLimitStore(vkapi)
    rlstore[user_id] = False
    err = ''
    try:
        vkapi.messages.send(user_id=user_id, message='Rate-limiting has been imposed on you.', random_id=0)
    except:
        err = 'But I can\'t send them messages, they may have blocked them or not started a chat with the bot.'
    return f'Enabled ratelimiting for user {utils.get_at_spec(user_id)}. {err}'

@requires_manager
@resolves_userspec
def getratelimit(user_id):
    rlstore = data_managers.DisabledRateLimitStore(vkapi)
    return f'Ratelimiting for user {utils.get_at_spec(user_id)} is ' + ('disabled' if rlstore[user_id] else 'enabled')

@requires_manager
def top_by_errors(how_many=10, user_id=None):
    how_many = int(how_many)
    data = stats.get_top_by_errors(how_many)
    outp = f'Top {len(data)} users by errors during rendering during last 7 days:\n\n'
    for index, item in enumerate(data):
        id, err_count = item
        outp += f'{index+1}. {utils.get_at_spec(id)} -- {err_count} errors\n'
    return outp

@requires_manager
def top_by_renders(how_many=10, user_id=None):
    how_many = int(how_many)
    data = stats.get_top_by_renders(how_many)
    outp = f'Top {len(data)} users by errors during rendering during last 7 days:\n\n'
    for index, item in enumerate(data):
        id, renders = item
        outp += f'{index+1}. {utils.get_at_spec(id)} -- {renders} renders\n'
    return outp

@requires_manager
def top_by_time(how_many=10, user_id=None):
    how_many = int(how_many)
    data = stats.get_top_by_time_taken(how_many)
    outp = f'Top {len(data)} users by rendering time during last 7 days:\n\n'
    for index, item in enumerate(data):
        id, time_taken = item
        outp += f'{index+1}. {utils.get_at_spec(id)} -- {time_taken} seconds\n'
    return outp
    
@requires_owner
@resolves_userspec
def promote(user_id):
    is_manager = data_managers.ManagerStore(vkapi)
    is_manager[user_id] = True
    err = ''
    try:
        vkapi.messages.send(user_id=user_id, message='You are now a manager.', random_id=0)
    except:
        err = 'But I can\'t send them messages, they may have blocked them or not started a chat with the bot.'
    return f'User {user.get_at_spec(user_id)} is now a manager. {err}'

@requires_owner
@resolves_userspec
def demote(user_id):
    is_manager = data_managers.ManagerStore(vkapi)
    is_manager[user_id] = False
    err = ''
    try:
        vkapi.messages.send(user_id=user_id, message='You are no longer a manager.', random_id=0)
    except:
        err = 'But I can\'t send them messages, they may have blocked them or not started a chat with the bot.'
    return f'User {utils.get_at_spec(user_id)} is no longer a manager. {err}'

@requires_owner
@resolves_userspec
def get_promoted(user_id):
    is_manager = data_managers.ManagerStore(vkapi)
    return f'User {user_id} is {"not" if not is_manager[user_id] else ""} a manager'

@requires_owner
def delete_error(uid):
    try:
        if uid.startswith(url_for('error_view', uid='', _external=True)):
            uid = uid.split(url_for('error_view', uid='', _external=True))[1]
        stats.delete_error(uid)
        return 'Deleted error '+uid
    except:
        return 'Error when deleting error: \n\n'+traceback.format_exc()

@requires_owner
def delete_all_errors():
    try:
        rows = stats.delete_all_errors()
        return 'Deleted '+str(rows)+' errors'
    except:
        return 'Error when deleting errors: \n\n'+traceback.format_exc()

@requires_owner
def show_errors(how_many=10):
    how_many = int(how_many)
    outp = ''
    for i in stats.list_latest_errors(how_many):
        outp += url_for('error_view', uid=i, _external=True)+'\n'
    return outp or 'No errors found. Great job!'

@requires_manager
def error_out():
    raise Exception('Testing exceptions')

slash_commands = {
    'help': slash_help,
    'reset-preamble': reset_preamble,
    'set-caption-code': set_caption_code,
    'set-dpi': set_dpi,
    'show-preamble': show_preamble,
    'add-preamble': add_preamble,
    'delete-preamble': delete_preamble,
    'set-render-time': set_caption_time,
    'ratelimit': ratelimit,
    'unratelimit': unratelimit,
    'getratelimit': getratelimit,
    'promote': promote,
    'demote': demote,
    'get-promoted': get_promoted,
    'top-by-errors': top_by_errors,
    'top-by-time': top_by_time,
    'top-by-renders': top_by_renders,
    'delete-error': delete_error,
    'delete-all-errors':delete_all_errors,
    'show-errors':show_errors,
    'error-out':error_out,
    }

def recv_message(data):
    message = data['object']['message']
    sender = message['from_id']
    reply_to = message['peer_id']
    
    def reply(t):
        vkapi.messages.send(peer_id=reply_to, message=(f'{utils.get_at_spec(sender)}: ' if sender!=reply_to else '')+t, random_id=0)

    if 'payload' in message:
        payload = json.loads( bytes(message['payload'], 'utf-8') )
        if 'command' in payload:
            if payload['command']=='start':
                reply('Welcome to InLaTeX! To begin, type a LaTeX expression to render it, or type "/help" for a command list.')
                return

    if 'action' in message:
        if 'type' in message['action']:
            if message['action']['type']=='chat_invite_user':
                reply('This is the InLaTeX bot. To use, please @-mention me and write an expression to render (like this: "@inlatexbot $E=mc^2$").\nFor more features, enter a private chat with me and type "/help".')
                return

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
                if answer:
                    reply(answer)
            except TypeError:
                reply('Wrong number of arguments for command, for command list type "/help".'+traceback.format_exc())
            except:
                reply('ERROR: see '+ERROR(traceback.format_exc(), reply_to, text))
        else:
            reply(f'Unknown command "{command[0]}", for list type "/help".')
        return

    rlstore = data_managers.DisabledRateLimitStore(vkapi)
    if not rlstore[sender]:
        RATE_LIM_INTERVAL = 30
        opt_man = data_managers.UserOptsManager(vkapi)
        if time.time() - opt_man.get_last_render_time(sender) < RATE_LIM_INTERVAL: # unregistered rate-limiting
            reply(f'It\'s been only {time.time() - opt_man.get_last_render_time(sender)}, please wait at least {RATE_LIM_INTERVAL} seconds before requesting next render')
            return

    workers = cel.control.inspect(timeout=0.75).ping()
    if workers is None:
        reply('''ERROR: No Celery workers responded to ping!
This is a serious problem!

The bot is currently unable to render images.
A report has been sent to the bot's admin.''')
        ERROR('Celery ping failed', sender, text)
        return

    latex_celery_tasks.ERROR = ERROR
    if sender == reply_to:
        latex_celery_tasks.render_for_user.apply_async((sender, text))
    else:
        latex_celery_tasks.render_for_groupchat.apply_async((sender, reply_to, text))

type_map = {
'confirmation': confirmation,
'message_new': recv_message,
}



@app.route('/')
def index():
    return render_template('index.html', random=random, allow_tracker='allow_tracker' in request.args)


@app.route('/api', methods=['POST'])
def api():
    data = 'failed on get_json'
    try:
        data = request.get_json(force=True)
        type = data['type']
        event_id = data['event_id']
        peer_id = config.owner_id
        try:
            peer_id = data['object']['message']['peer_id']
        except:
            pass
        if not is_unique_event(event_id, data, peer_id, vkapi):
            return 'ok'
        fun = type_map.get(type, default_data_handler)
        res = fun(data)
        if res is None:
            return 'ok'
        else:
            return res
    except:
        traceback.print_exc()
        ERROR(traceback.format_exc(), None, str(data))
        return 'ok'

if __name__ == '__main__':
    app.run('0.0.0.0', 5000, True)
