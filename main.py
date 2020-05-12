import config
from peewee import *
from flask import Flask, request


database = MySQLDatabase('inlatex', user='inlatex', password='inlatex')

app = Flask(__name__)



def confirmation(data):
    return config.confirmation_string


type_map = {
'confirmation': confirmation
}


@app.route('/')
def index():
    return 'Hello LaTeX!'

@app.route('/api', methods=['POST'])
def api():
    data = request.get_json(force=True)
    type = data['type']
    fun = type_map.get(type, lambda x:None)
    res = fun(data)
    if res is None:
        return 'ok'
    else:
        return res

