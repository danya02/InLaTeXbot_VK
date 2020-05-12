from celery import Celery
import vk_api
import config
from latex_renderer import LatexConverter
import uuid
import traceback

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
        #doc = upload.document_message(pdf, peer_id=sender)[0]
        api.messages.send(peer_id=sender, attachment=f'photo{photo["owner_id"]}_{photo["id"]}', random_id=0)
        #api.messages.send(peer_id=sender, attachment=f'doc{doc["owner_id"]}_{doc["id"]}', random_id=0)
    except:
        api.messages.send(peer_id=sender, message='ERROR\n'+traceback.format_exc(), random_id=0)
@cel.task
def render_for_groupchat(sender, reply_to, text):
    try:
        png = conv.convertExpressionToPng(text, sender, str(uuid.uuid4()))
        api.messages.send(peer_id=reply_to, message='@id'+str(sender)+' sent: '+text, random_id=0)
    except:
        api.messages.send(peer_id=sender, message='ERROR\n'+traceback.format_exc(), random_id=0)
