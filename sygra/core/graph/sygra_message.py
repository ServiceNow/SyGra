class SygraMessage:
    """
    This class holds the backend message.
    """

    def __init__(self, msg):
        self._message = msg

    @property
    def message(self):
        return self._message
