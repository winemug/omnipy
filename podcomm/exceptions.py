
class OmnipyError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message

    def __str__(self):
        self.__traceback__.print_tb()
        return "%s: %s\n\nContext: %s\nTraceback: %s\n" % (self.__class__.__name__, self.error_message,
                                                           self.__context__, self.__traceback__.format_exc())


class RileyLinkError(OmnipyError):
    def __init__(self, message="Unknown RL error", err_code=None):
        OmnipyError.__init__(self, message)
        self.err_code = err_code

    def __str__(self):
        return super.__str__


class ProtocolError(OmnipyError):
    def __init__(self, message="Unknown protocol error"):
        OmnipyError.__init__(self, message)

    def __str__(self):
        return super.__str__


class TransmissionOutOfSyncError(ProtocolError):
    def __init__(self, message="Transmission out of sync error"):
        OmnipyError.__init__(self, message)

    def __str__(self):
        return super.__str__


class PdmError(OmnipyError):
    def __init__(self, message="Unknown pdm error"):
        OmnipyError.__init__(self, message)

    def __str__(self):
        return super.__str__


class PdmBusyError(PdmError):
    def __init__(self, message="Pdm is busy."):
        OmnipyError.__init__(self, message)
