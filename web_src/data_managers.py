import hmac
import uuid
import json
import time
import os

PREAMBLE_PARTS_COUNT = 512

DEFAULT_PREAMBLE = '''
\\documentclass{article}
\\usepackage[a6paper]{geometry}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage[russian]{babel}
\\usepackage{textcomp}
\\usepackage{amsmath}
\\pagenumbering{gobble}
'''

HMAC_SECRET = bytes(os.getenv('HMAC_SECRET'), 'utf-8')

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
        data = self.api.storage.get(keys=','.join(self.keys), user_id=user_id)
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
        outp = []
        for line in preamble_arr:
            if line:
                outp.append(line)
        return outp
    
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
            self.api.storage.set(key='code_in_caption', value='True', user_id=user_id)
        else:
            self.api.storage.set(key='code_in_caption', value='', user_id=user_id)

    def get_time_in_caption(self, user_id):
        return bool(self.api.storage.get(user_id=user_id, key='time_in_caption'))
    
    def set_time_in_caption(self, user_id, value):
        if value:
            self.api.storage.set(key='time_in_caption', value='True', user_id=user_id)
        else:
            self.api.storage.set(key='time_in_caption', value='', user_id=user_id)

    def get_last_render_time(self, user_id):
        return int(self.api.storage.get(key='last_render_time', user_id=user_id) or 0)

    def set_last_render_time(self, user_id, val):
        self.api.storage.set(key='last_render_time', user_id=user_id, value=int(val))

class SecretProtectedPropertyStore:
    PROPERTY = 'seeecret',
    BOOLEAN = False
    def __init__(self, api):
        self.api = api

    def get_storage_key(self, user_id):
        if user_id % 2 == 0: # no particular reason, but more unpredictability is better
            to_hash = str(user_id)+self.PROPERTY
        else:
            to_hash = self.PROPERTY+str(user_id)
        digest = hmac.digest(HMAC_SECRET, bytes( to_hash, 'utf-8' ), 'sha1').hexdigest()
        return self.PROPERTY+'-'+digest

    def __getitem__(self, user_id):
        if self.BOOLEAN:
            return bool(self.api.storage.get(key=self.get_storage_key(user_id), user_id=user_id))
        else:
            return self.api.storage.get(key=self.get_storage_key(user_id), user_id=user_id)

    def __setitem__(self, user_id, value):
        if self.BOOLEAN:
            if value:
                value = hmac.new(HMAC_SECRET, bytes( str(uuid.uuid4()), 'utf-8' ), 'sha1').hexdigest() # again, no reason, just make it look mysterious
            else:
                value = ''
        self.api.storage.set(user_id=user_id, key=self.get_storage_key(user_id), value=value)

class ManagerStore(SecretProtectedPropertyStore):
    PROPERTY = 'manager'
    BOOLEAN = True

class DisabledRateLimitStore(SecretProtectedPropertyStore):
    PROPERTY = 'disableRateLimit'
    BOOLEAN = True

class SignedValuePropertyStore:
    PROPERTY = 'seecret'
    DEFAULT_ON_HMAC_FAIL = None
    DEFAULT_ON_NO_SEP = None
    SEPARATOR = 'jL~k4F-j^b6!tU+g'

    def __init__(self, api):
        self.api = api

    def get_default_on_hmac_fail(self):
        if callable(self.DEFAULT_ON_HMAC_FAIL):
            return self.DEFAULT_ON_HMAC_FAIL()
        else:
            return self.DEFAULT_ON_HMAC_FAIL
    
    def get_default_on_no_sep(self):
        if callable(self.DEFAULT_ON_NO_SEP):
            return self.DEFAULT_ON_NO_SEP()
        else:
            return self.DEFAULT_ON_NO_SEP

    def __getitem__(self, user_id):
        res = self.api.storage.get(key=self.PROPERTY, user_id=user_id)
        if self.SEPARATOR not in res: # may mean that the user has never used the bot before, but may also mean that they've removed this key. How do we protect against that?
            return self.get_default_on_no_sep()

        data, stored_hmac = res.split(self.SEPARATOR)
        data = bytes(data, 'utf-8')
        my_hmac = hmac.new(HMAC_SECRET+bytes(str(user_id), 'utf-8'), data, 'sha1').hexdigest()
        if hmac.compare_digest(stored_hmac, my_hmac):
            data = json.loads(data) # do not check for errors here, if it passed HMAC check then we know it came from us
        else:
            data = self.get_default_on_hmac_fail()
        return data

    def __setitem__(self, user_id, value):
        data = json.dumps(value)
        signature = hmac.new(HMAC_SECRET+bytes(str(user_id), 'utf-8'), data, 'sha1').hexdigest()
        data = str(data, 'utf-8')
        res = self.api.storage.set(key=self.PROPERTY, user_id=user_id, value=data + self.SEPARATOR + signature)

