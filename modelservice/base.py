class Registry(object):
    _registry = {}

    def register(self, func, key):
        if key in self._registry:
            raise ValueError('Key `{}` is already registered.'.format(key))
        self._registry[key] = func

    def unregister(self, key):
        self._registry.pop(key)

    def __getitem__(self, key):
        return self._registry[key]


class WampRegistry(Registry):
    OptionsClass = None

    def register(self, func, key, **kwargs):
        if key in self._registry:
            raise ValueError('Key `{}` is already registered.'.format(key))
        self._registry[key] = {
            'func': func,
            'options': self.OptionsClass(**kwargs),
            'name': key,
        }


class RegisterDecorator(object):
    registry = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        super(RegisterDecorator, self).__init__()

    def __call__(self, func):
        self.registry.register(func, *self.args, **self.kwargs)

        return func
