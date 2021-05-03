from celery import Celery
import vk_api
try:
    from latex_renderer import LatexConverter
except ModuleNotFoundError:  # imported from web code, so renderer module not used
    pass
import uuid
import traceback
import data_managers
import time
import stats
import utils
import os


cel = Celery('latex_celery_tasks', broker=f'amqp://guest:guest@broker')
vk_session = vk_api.VkApi(token=os.getenv('VK_ACCESS_TOKEN'))
OWNER_ID = int(os.getenv('OWNER_ID'))
api = vk_session.get_api()
try:
    conv = LatexConverter(api)
except NameError:  # import from above failed, so this is imported from web code and serves as a procedure reference for celery rather than being executed
    pass
utils = utils.VKUtilities(api)


def ERROR(trace, user_id=None, text=None):
    uid = stats.record_error(trace, user_id, text)
    url = os.getenv('SERVER_NAME') + '/view-error/' + uid  # Change this line if you change the line in the web app.
    vkapi.messages.send(peer_id=OWNER_ID, message='Unknown error encountered! Details at '+url, random_id=0)
    return url

def upload_doc(doc, peer_id, upload): # because vk_api is broken
    # step 1: get server
    server = api.docs.getMessagesUploadServer(peer_id=peer_id)['upload_url']

    # step 2: upload to server, get token
    resp = upload.http.post(server, files={'file': ('expression.pdf', doc.read())}).json()

    # step 3: save the file by token
    resp.update({'title': 'LaTeX expression', 'type': 'doc'})
    doc = api.docs.save(**resp)['doc']
    return f'doc{doc["owner_id"]}_{doc["id"]}'


@cel.task
def render_for_user(sender, text):
    error = False
    ttr = 0
    try:
        t1 = time.time()
        png, pdf = conv.convertExpressionToPng(text, sender, str(uuid.uuid4()), returnPdf=True)
        ttr = time.time()-t1
        upload = vk_api.upload.VkUpload(vk_session)


        photo = upload.photo_messages(png)[0]
        photo_send_kwargs = {'peer_id':sender, 'attachment':f'photo{photo["owner_id"]}_{photo["id"]}', 'random_id':0, 'message':''}


        opt_man = data_managers.UserOptsManager(api)
        cic = opt_man.get_code_in_caption(sender)
        tic = opt_man.get_time_in_caption(sender)
        if cic:
            photo_send_kwargs.update({'message': text})
        if tic:
            if photo_send_kwargs['message']:
                photo_send_kwargs['message'] += f' (rendered in {ttr} seconds)'
            else:
                photo_send_kwargs['message'] = f'Rendered in {ttr} seconds'

        doc_send_kwargs = {'peer_id': sender, 'attachment': upload_doc(pdf, sender, upload), 'message': photo_send_kwargs['message'], 'random_id': 0}
        api.messages.send(**photo_send_kwargs)
        api.messages.send(**doc_send_kwargs)
        opt_man.set_last_render_time(sender, time.time())
    except ValueError as e:
        api.messages.send(peer_id=sender, message='LaTeX error:\n'+e.args[0], random_id=0)
        error = True
    except:
        api.messages.send(peer_id=sender, message='ERROR: see '+ERROR(traceback.format_exc(), sender, text),  random_id=0)
        error = True
    finally:
        stats.record_render(sender, ttr, error)
        stats.delete_older_than() 

@cel.task
def render_for_groupchat(sender, reply_to, text):
    ttr = 0
    error = False
    try:
        t1 = time.time()
        png = conv.convertExpressionToPng(text, sender, str(uuid.uuid4()))
        ttr = time.time()-t1

        upload = vk_api.upload.VkUpload(vk_session)
        photo = upload.photo_messages(png)[0]
        photo_send_kwargs = {'peer_id':reply_to, 'attachment':f'photo{photo["owner_id"]}_{photo["id"]}', 'random_id':0}

        opt_man = data_managers.UserOptsManager(api)
        cic = opt_man.get_code_in_caption(sender)
        tic = opt_man.get_time_in_caption(sender)
        if cic and tic:
            photo_send_kwargs.update({'message': f'{utils.get_at_spec(sender)}: {text} (rendered in {ttr} seconds)'})
        elif tic:
            photo_send_kwargs.update({'message': f'{utils.get_at_spec(sender)}: rendered in {ttr} seconds'})
        elif cic:
            photo_send_kwargs.update({'message': f'{utils.get_at_spec(sender)}: {text}'})
        else:
            photo_send_kwargs.update({'message': f'{utils.get_at_spec(sender)}'})

        api.messages.send(**photo_send_kwargs)
        opt_man.set_last_render_time(sender, time.time())
    except ValueError as e:
        api.messages.send(peer_id=reply_to, message=f'{utils.get_at_spec(sender)}: LaTeX error:\n'+e.args[0], random_id=0)
        error = True
    except:
        api.messages.send(peer_id=reply_to, message='{utils.get_at_spec(sender)}: ERROR, see '+ERROR(traceback.format_exc(), sender, text),  random_id=0)
        error = True
    finally:
        stats.record_render(sender, ttr, error)
        stats.delete_older_than() 
