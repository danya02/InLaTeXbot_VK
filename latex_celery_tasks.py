from celery import Celery
import vk_api
import config
from latex_renderer import LatexConverter
import uuid
import traceback
import data_managers
import time
import stats

cel = Celery('latex_celery_tasks', broker='redis://localhost')
vk_session = vk_api.VkApi(token=config.access_token)
api = vk_session.get_api()
conv = LatexConverter(api)

def ERROR(*args): # this is where main.py will put their error function.
    pass

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

        api.messages.send(**photo_send_kwargs)
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
            photo_send_kwargs.update({'message': f'@id{sender}: {text} (rendered in {ttr} seconds)'})
        elif tic:
            photo_send_kwargs.update({'message': f'@id{sender}: rendered in {ttr} seconds'})
        elif cic:
            photo_send_kwargs.update({'message': f'@id{sender}: {text}'})
        else:
            photo_send_kwargs.update({'message': f'@id{sender}'})

        api.messages.send(**photo_send_kwargs)
        opt_man.set_last_render_time(sender, time.time())
    except ValueError as e:
        api.messages.send(peer_id=reply_to, message=f'@id{sender}: LaTeX error:\n'+e.args[0], random_id=0)
        error = True
    except:
        api.messages.send(peer_id=reply_to, message='@id{sender}: ERROR, see '+ERROR(traceback.format_exc(), sender, text),  random_id=0)
        error = True
    finally:
        stats.record_render(sender, ttr, error)
        stats.delete_older_than() 
