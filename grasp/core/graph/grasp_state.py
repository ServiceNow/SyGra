from typing import TypedDict


class GraspState(TypedDict):
    """
    This class defines predefined state variables/schema.

    This will be implemented in derived class, which will be used to inject other state variables.
    Base class is only added for readability and keeping langgraph decoupled from platform
    """

    def __init__(self):
        # this is added to complete the class
        return
