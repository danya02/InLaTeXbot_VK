from peewee import *
import datetime
import uuid
import os

dbase = MySQLDatabase(os.getenv('MYSQL_DATABASE'), user='root', password=os.getenv('MYSQL_ROOT_PASSWORD'), host='database')

class MyModel(Model):
    class Meta:
        database = dbase


class User(MyModel):
    user_id = IntegerField(primary_key=True)

class Render(MyModel):
    user = ForeignKeyField(User)
    time_taken = FloatField()
    when = DateTimeField(default=datetime.datetime.now)
    was_error = BooleanField(default=False)

class Error(MyModel):
    uuid = UUIDField(default=uuid.uuid4)
    trace = TextField()
    associated_user_id = IntegerField(null=True) # may also be a ForeignKeyField, but better not to defend against errors here
    caused_by_text = TextField(null=True)
    when = DateTimeField(default=datetime.datetime.now)

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

dbase.connect()
with dbase.atomic():
    dbase.create_tables([User, Render, Error])
dbase.close()

@uses_dbase
def delete_older_than(days=7, seconds=0):
    delta = datetime.timedelta(days, seconds)
    cutoff_date = datetime.datetime.now() - delta
    return Render.delete().where(Render.when < cutoff_date).execute()

@uses_dbase
def get_top_by_time_taken(num=10):
    query = User.select(User, fn.Sum(Render.time_taken).alias('total_time')).join(Render, JOIN.LEFT_OUTER).group_by(User).order_by(SQL('total_time').desc()).limit(num)
    out_list = []
    for user in query:
        out_list.append( (user.user_id, user.total_time) )
    return out_list

@uses_dbase
def get_top_by_errors(num=10):
    query = User.select(User, fn.Count(Render.id).alias('errors')).join(Render).where(Render.was_error == True).group_by(User).order_by(SQL('errors').desc()).limit(num)
    out_list = []
    for user in query:
        out_list.append( (user.user_id, user.errors) )
    return out_list

@uses_dbase
def get_top_by_renders(num=10):
    query = User.select(User, fn.Count(Render.id).alias('renders')).join(Render).group_by(User).order_by(SQL('renders').desc()).limit(num)
    out_list = []
    for user in query:
        out_list.append( (user.user_id, user.renders) )
    return out_list

@uses_dbase
def record_render(user_id, time_taken, error=False):
    user = User.get_or_create(user_id=user_id)[0]
    Render.create(user=user, time_taken=time_taken, was_error=error)

@uses_dbase
def record_error(trace, user_id=None, text=None):
    err = Error.create(trace=trace, associated_user_id=user_id, caused_by_text=text)
    return str(err.uuid)

@uses_dbase
def get_error(uid):
    return Error.get(uuid=uid)

@uses_dbase
def delete_error(uid):
    Error.get(uuid=uid).delete_instance()

@uses_dbase
def delete_all_errors():
    return Error.delete().execute()

@uses_dbase
def list_latest_errors(how_many=10):
    return [i.uuid for i in Error.select().order_by(Error.when.desc()).limit(how_many)]
