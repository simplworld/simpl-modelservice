from modelservice import conf

from genericclient_base.exceptions import HTTPError


class SubscriptionAlreadyExists(Exception):
    def __init__(self, response, *args, **kwargs):
        self.response = response
        super(SubscriptionAlreadyExists, self).__init__(*args, **kwargs)


async def subscribe(api_session, prefix, callback=None):
    if callback is None:
        callback = conf.get_callback_url()
    try:
        subscription = await api_session.hooks.create({
            'event': '{}.*'.format(prefix),
            'url': callback,
        })
        return subscription
    except HTTPError as e:
        if e.response.status == 400:
            response_data = await e.response.json()
            if 'url' in response_data:
                raise ValueError(
                    'callback url not valid: `{}`.'.format(callback))
            raise SubscriptionAlreadyExists(e.response, callback)

    raise ValueError("could not register webhooks")


async def unsubscribe(api_session, subscription):
    await api_session.hooks.delete(subscription)
