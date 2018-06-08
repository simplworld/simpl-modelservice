from modelservice.webhooks import hook


@hook('ADD_USER')
def add_user(**payload):
    """Just a test"""
    pass
