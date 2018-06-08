from .registry import methods_registry


class ScopeInspector(object):
    @staticmethod
    def marked_methods(instance, key):
        methods = []
        for m in getattr(methods_registry, key):
            # The method was inserted in registry at declaration time, which
            # means it's unbound. Let's get a bound copy
            bound_method = m.method.__get__(instance, instance.__class__)
            # Check that the bound method actually belongs to the instance.
            if bound_method == getattr(instance, m.name, None):
                methods.append(
                    (m.name, bound_method, m.options)
                )
        return methods

    @staticmethod
    def callees(instance):
        return ScopeInspector.marked_methods(instance, 'registered')

    @staticmethod
    def subscribers(instance):
        return ScopeInspector.marked_methods(instance, 'subscribed')

    @staticmethod
    def hooks(instance):
        return ScopeInspector.marked_methods(instance, 'hooked')
