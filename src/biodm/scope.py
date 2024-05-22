from enum import Flag

class Scope(Flag):
    """Runtime Feature Flag."""
    PROD = 0
    DEBUG = 1
    TEST = 2
