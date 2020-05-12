from celery import Celery
import vk_api
import config
from latex_renderer import LatexConverter

cel = Celery('latex_celery_tasks', broker='redis://localhost')
vk_session = vk_api.VkApi(token=config.access_token)
api = vk_session.get_api()
conv = LatexConverter()

@cel.task
def render_for_user(sender, text):
    png, pdf = conv.convertExpressionToPng(text, userId, sessionId, returnPdf=True)
    api.messages.send(peer_id=sender, message='You sent: '+text, random_id=0)

@cel.task
def render_for_groupchat(sender, reply_to, text):
    png = conv.convertExpressionToPng(text, userId, sessionId)
    api.messages.send(peer_id=reply_to, message='@id'+str(sender)+' sent: '+text, random_id=0)


