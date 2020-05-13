from celery import Celery
import vk_api
import config
from latex_renderer import LatexConverter
import uuid
import traceback
import data_managers

cel = Celery('latex_celery_tasks', broker='redis://localhost')
vk_session = vk_api.VkApi(token=config.access_token)
api = vk_session.get_api()
conv = LatexConverter(api)

@cel.task
def render_for_user(sender, text):
    try:
        png, pdf = conv.convertExpressionToPng(text, sender, str(uuid.uuid4()), returnPdf=True)
        upload = vk_api.upload.VkUpload(vk_session)
        photo = upload.photo_messages(png)[0]
        photo_send_kwargs = {'peer_id':sender, 'attachment':f'photo{photo["owner_id"]}_{photo["id"]}', 'random_id':0}

        opt_man = data_managers.UserOptsManager(api)
        cic = opt_man.get_code_in_caption(sender)
        if cic:
            photo_send_kwargs.update({'message': text})

        api.messages.send(**photo_send_kwargs)
    except ValueError as e:
        api.messages.send(peer_id=sender, message='LaTeX error:\n'+e.args[0], random_id=0)
    except:
        api.messages.send(peer_id=sender, message='ERROR\n'+traceback.format_exc(), random_id=0)
@cel.task
def render_for_groupchat(sender, reply_to, text):
    try:
        png = conv.convertExpressionToPng(text, sender, str(uuid.uuid4()))

        upload = vk_api.upload.VkUpload(vk_session)
        photo = upload.photo_messages(png)[0]
        photo_send_kwargs = {'peer_id':reply_to, 'attachment':f'photo{photo["owner_id"]}_{photo["id"]}', 'random_id':0}

        opt_man = data_managers.UserOptsManager(api)
        cic = opt_man.get_code_in_caption(sender)
        if cic:
            photo_send_kwargs.update({'message': f'@id{sender}: {text}'})
        else:
            photo_send_kwargs.update({'message': f'@id{sender}'})

        api.messages.send(**photo_send_kwargs)
    except ValueError as e:
        api.messages.send(peer_id=reply_to, message=f'@id{sender}: LaTeX error:\n'+e.args[0], random_id=0)
    except:
        api.messages.send(peer_id=reply_to, message=f'@id{sender}: ERROR\n'+traceback.format_exc(), random_id=0)