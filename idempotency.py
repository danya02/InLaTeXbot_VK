from peewee import *
import datetime
import json
import config

dbase = MySQLDatabase('inlatex', user='inlatex', password='inlatex')

class MyModel(Model):
    class Meta:
        database = dbase

class VKEvent(MyModel):
    date = DatetimeField(default=datetime.datetime.now)
    event_id = CharField(unique=True)
    content = TextField()

def uses_dbase(fn):
    def wrapper(*args, **kwargs):
        try:
            dbase.connect()
        except OperationalError: # may mean either failed connecting, or opening connection failed -- how to distinguish?
            pass
        try:
            res = fn(*args, **kwargs)
            return res
        finally:
            dbase.close()
    return wrapper


user_facing_message='''
We just received an event from VK that matches an event we received at {date}, so we are not repeating this request. If your request was not acknowledged, please send your message again.
This probably means that VK considers this server to be too slow. Sorry :(
'''.strip()

@uses_dbase
def is_unique_event(event_id, event, peer_id, vkapi):
    dbase.create_tables([VKEvent])

    def send(to_whom, what):
        vkapi.messages.send(peer_id=to_whom, random_id=0, message=what)
    def inform_user(existing_event):
        send(peer_id, user_facing_message.format(date=existing_event.date.ctime()))
        send(config.owner_id, 'Repeat event received, original at '+existing_event.date.ctime()+': '+existing_event.content)

    # Remove old entries    
    delta = datetime.timedelta(1, 0)  # keep events for 1 day
    cutoff_date = datetime.datetime.now() - delta
    VKEvent.delete().where(VKEvent.date < cutoff_date).execute()

    existing_event = VKEvent.get_or_none(event_id=event_id)
    if existing_event is None:
        try:
            VKEvent.create(event_id=event_id, content=json.dumps(event))
        except IntegrityError:
            inform_user(existing_event)
            return False
        return True
    else:
        inform_user(existing_event)
        return False
