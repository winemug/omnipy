class OmnipyError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message

    def __str__(self):
        return "%s: %s\n\nContext: %s\n" % (self.__class__.__name__, self.error_message, self.__context__)


class RileyLinkError(OmnipyError):
    def __init__(self, message="Unknown", err_code=None):
        OmnipyError.__init__(self, message)
        self.err_code = err_code


class ProtocolError(OmnipyError):
    pass


class PdmError(OmnipyError):
    pass


class PdmBusyError(PdmError):
    pass