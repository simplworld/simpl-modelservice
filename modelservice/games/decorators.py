import inspect
from functools import wraps

from .registry import methods_registry

default_registration_options = {
    'match': 'prefix',
    'details_arg': 'details'
}


def get_user_details(details):
    try:
        user_id = details.caller_authid
    except AttributeError:
        user_id = details.publisher_authid

    try:
        role = details.caller_authrole
    except AttributeError:
        role = details.publisher_authrole

    return user_id, role


def mark(attr, *args, **kwargs):
    if callable(args[0]):
        function = args[0]
        if len(args) > 1:
            topic = args[1]
        else:
            topic = None
    else:
        function = None
        if len(args) > 0:
            topic = args[0]
        else:
            topic = None

    def decorator(func):
        @wraps(func)
        async def wrap(scope, *_args, **_kwargs):
            details = _kwargs.get('details', None)
            user = None

            if details is not None:
                user_id, role = get_user_details(details)

                # Profilers can override the user id for profiling purposes
                if role == 'profiler':
                    if 'user_email' in _kwargs:
                        email = _kwargs.pop('user_email')
                        user = await scope.storage.get_user(email=email)
                elif user_id is not None:
                    user = await scope.storage.get_user(id=user_id)

            _kwargs['user'] = user

            try:
                if inspect.iscoroutinefunction(func):
                    return await func(scope, *_args, **_kwargs)
                else:
                    return func(scope, *_args, **_kwargs)
            except Exception as e:
                # Monkey-patch the exception by adding the user, so that we can
                # publish it via websocket to a user-specific topic
                e.user = user
                raise

        value = topic or func.__name__
        setattr(wrap, attr, value)
        registration_options = default_registration_options.copy()
        registration_options.update(kwargs)
        wrap.registration_options = registration_options
        getattr(methods_registry, attr).add(
            method=wrap,
            name=func.__name__,
            options=registration_options,
        )

        return wrap

    if function:
        return decorator(function)
    return decorator


def subscribe(*args, **kwargs):
    return mark('subscribed', *args, **kwargs)


def register(*args, **kwargs):
    return mark('registered', *args, **kwargs)


def hook(*args, **kwargs):
    return mark('hooked', *args, **kwargs)
