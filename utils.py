class VKUtilities:
    def __init__(self, api):
        self.api = api

    def get_at_spec(self, user_id):
        data = self.api.users.get(user_ids=user_id, fields='screen_name')[0]
        return '@'+data['screen_name']
    
    def resolve_to_user_id(self, at_spec):
        if at_spec.starts_with('@'):
            try:
                data = self.api.users.get(user_ids=at_spec[1:], fields='screen_name')[0]
                return data['id']
            except:
                safe_str = at_spec.replace('@', '(at)').replace('[', '(lbrak)').replace(']','(rbrak)').replace('|', '(pipe)')
                return ValueError('Failed to resolve "{safe_str}" (which is a plain @-mention)')
        elif at_spec.starts_with('['):
            try:
                resolved = int(userspec.split('id')[1].split('|')[0])
                data = self.api.users.get(user_ids=resolved)
                return resolved
            except:
                safe_str = at_spec.replace('@', '(at)').replace('[', '(lbrak)').replace(']','(rbrak)').replace('|', '(pipe)')
                return ValueError('Failed to resolve "{safe_str}" (which is a link-style)')


