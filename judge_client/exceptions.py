class JudgeError:
    def __init__(self, detail: str):
        self.detail = detail

    def __str__(self):
        return f"{self.__class__.__name__}: {repr(self.detail)}"


class JudgeConnectionError(IOError, JudgeError):
    pass


class UnknownLanguageError(ValueError, JudgeError):
    pass


class ProtocolError(ValueError):
    def __init__(self, message: str, protocol: str):
        self.message = message
        self.protocol = protocol

    def __str__(self):
        return f"{self.__class__.__name__}: {repr(self.message)}\n{self.protocol}"


class ProtocolCorruptedError(ProtocolError):
    pass


class ProtocolFormatError(ProtocolError):
    pass
