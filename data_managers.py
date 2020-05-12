import config
import hmac
import uuid

PREAMBLE_PARTS_COUNT = 512

DEFAULT_PREAMBLE = '''
\documentclass{article}
\usepackage[a6paper]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{textcomp}
\usepackage{lastpage}
\usepackage{amsmath}
\usepackage{physics}
\usepackage{lipsum}
\pagenumbering{gobble}
'''

class PreambleManager:
    def __init__(self, api):
        self.api = api

    def get(self, user_id):
        preamble = self.strip_empty(self.get_as_list(user_id))
        preamble = '\n'.join(preamble)
        return preamble

    @property
    def keys(self):
        key = []
        for i in range(PREAMBLE_PARTS_COUNT):
            key.append(f'preamble_part_{i}')
        return key

    @property
    def default_preamble(self):
        return DEFAULT_PREAMBLE.strip().split('\n')

    def get_as_list(self, user_id, init_if_empty=True):
        data = self.api.storage.get(keys=','.join(self.keys))
        preamble_arr = []
        for element in data:
            preamble_arr.append(element['value'])
        if init_if_empty:
            if len(self.strip_empty(preamble_arr)) == 0:
                self.set_list(user_id, self.default_preamble)
                return self.pad_with_empty(self.default_preamble)
        return preamble_arr

    def pad_with_empty(self, preamble_arr):
        if len(preamble_arr)>PREAMBLE_PARTS_COUNT:
            raise ValueError(f'There are too many parts in the preamble! Max is {PREAMBLE_PARTS_COUNT}, current is {len(preamble_arr)}')
        while len(preamble_arr)<PREAMBLE_PARTS_COUNT:
            preamble_arr.append('')
        return preamble_arr

    def strip_empty(self, preamble_arr):
        return [line in preamble_arr if line]
    
    def shift_all_to_start(self, preamble_arr):
        return self.pad_with_empty(self.strip_empty(preamble_arr))

    def set_list(self, user_id, preamble_arr):
        preamble_arr = self.shift_all_to_start(preamble_arr)
        old_preamble = self.get_as_list(user_id, init_if_empty=False)
        for key, old, new in zip(self.keys, old_preamble, preamble_arr):
            if old!=new:
                self.api.storage.set(user_id=user_id, key=key, value=new)

    def delete(self, user_id, index):
        arr = self.get_as_list(user_id)
        arr.remove(index)
        self.set_list(user_id, arr)
    
    def insert(self, user_id, new_line):
        arr = self.strip_empty(self.get_as_list())
        arr.append(new_line)
        self.set_list(user_id, arr)
        return len(arr)-1 # index of new-added element

class UserOptsManager:
    def __init__(self, api):
        self.api = api

    def get_dpi(self, user_id):
        return int(self.api.storage.get(key='dpi', user_id=user_id) or 300)

    def set_dpi(self, user_id, value):
        self.api.storage.set(key='dpi', user_id=user_id, value=value)

    def get_code_in_caption(self, user_id):
        return bool(self.api.storage.get(user_id=user_id, key='code_in_caption'))
    
    def set_code_in_caption(self, user_id, value):
        if value:
            self.api.storage.set(key='code_in_caption', value='True')
        else:
            self.api.storage.set(key='code_in_caption', value='')

        return int(self.api.storage.get(key='last_render_time', user_id=user_id) or 0)

class SecretProtectedPropertyStore:
    CONFIG = {
            'property': 'seeecret',
            'is_bool': False
            }
    def __init__(self, api):
        self.api = api

    def get_storage_key(self, user_id):
        if user_id % 2 == 0: # no particular reason, but more unpredictability is better
            to_hash = str(user_id)+CONFIG['property']
        else:
            to_hash = CONFIG['property']+str(user_id)
        digest = hmac.HMAC(config.secret, bytes( to_hash, 'utf-8' )).hexdigest()
        return CONFIG['property']+'-'+digest

    def __getitem__(self, user_id):
        if CONFIG['is_bool']:
            return bool(self.api.get(key=self.get_storage_key(user_id)))
        else:
            return self.api.get(key=self.get_storage_key(user_id))

    def __setitem__(self, user_id, value):
        if CONFIG['is_bool']:
            if value:
                value = hmac.HMAC(config.secret, bytes( str(uuid.uuid4()), 'utf-8' )).hexdigest() # again, no reason, just make it look mysterious
            else:
                value = ''
        self.api.set(key=self.get_storage_key(user_id), value=value)

class ManagerStore(SecretProtectedPropertyStore):
    CONFIG={'property': 'manager', 'is_bool':True}

class DisabledRateLimitStore(SecretProtectedPropertyStore):
    CONFIG={'property': 'manager', 'is_bool':True}
