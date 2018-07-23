from autobahn import wamp
from autobahn.wamp.exception import ApplicationError


class ScopesNotLoaded(Exception):
    pass


class ScopeNotFound(Exception):
    pass


class ParentScopeNotFound(ScopeNotFound):
    pass


class MultipleScopesFound(Exception):
    pass


CHANGE_PHASE_ERROR_URI = u"application.error.change_phase"


@wamp.error(CHANGE_PHASE_ERROR_URI)
class ChangePhaseException(ApplicationError):
    def __init__(self, *args, **kwargs):
        return super(ChangePhaseException, self).__init__(
            CHANGE_PHASE_ERROR_URI, *args, **kwargs)


FORM_ERROR_URI = u"application.error.validation_error"


@wamp.error(FORM_ERROR_URI)
class FormError(ApplicationError):
    """
    Raise this exception to have the error shown by simpl-react.

    :param errors: a dict of errors. Keys will map to the fields' name, values
    will be the error string to be shows. The special key ``'_error'`` is used
    errors that are not specific to a single field
    :type errors: dict

    Usage::

        raise FormError({'email': 'user already exists.', '_error': 'Registration Failed.'})
    """

    def __init__(self, form_name, errors):
        return super(FormError, self).__init__(FORM_ERROR_URI, form_name,
                                               errors)
