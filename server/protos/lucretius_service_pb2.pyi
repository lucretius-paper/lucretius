from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ConnectionRequest(_message.Message):
    __slots__ = ("application_name", "pid")
    APPLICATION_NAME_FIELD_NUMBER: _ClassVar[int]
    PID_FIELD_NUMBER: _ClassVar[int]
    application_name: str
    pid: int
    def __init__(self, application_name: _Optional[str] = ..., pid: _Optional[int] = ...) -> None: ...

class ConnectionResponse(_message.Message):
    __slots__ = ("is_available",)
    IS_AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    is_available: bool
    def __init__(self, is_available: bool = ...) -> None: ...

class StartRequest(_message.Message):
    __slots__ = ("pid",)
    PID_FIELD_NUMBER: _ClassVar[int]
    pid: int
    def __init__(self, pid: _Optional[int] = ...) -> None: ...

class StartResponse(_message.Message):
    __slots__ = ("can_run",)
    CAN_RUN_FIELD_NUMBER: _ClassVar[int]
    can_run: bool
    def __init__(self, can_run: bool = ...) -> None: ...

class FinishedNotification(_message.Message):
    __slots__ = ("pid",)
    PID_FIELD_NUMBER: _ClassVar[int]
    pid: int
    def __init__(self, pid: _Optional[int] = ...) -> None: ...

class DoneResponse(_message.Message):
    __slots__ = ("am_done",)
    AM_DONE_FIELD_NUMBER: _ClassVar[int]
    am_done: bool
    def __init__(self, am_done: bool = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
