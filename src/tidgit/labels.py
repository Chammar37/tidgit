from enum import Enum


class Label(str, Enum):
    CONFLICT = "■"
    STAGED = "●"
    UNSTAGED = "●"
    NEW_FILE = "●"
    DELETED = "●"
    CHANGES = "●"
