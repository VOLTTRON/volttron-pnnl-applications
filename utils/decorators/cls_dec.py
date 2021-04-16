# cls_decs.py
from .fn_decs import timer

def dec_all_methods(*decs):
    '''
    Applies arbitrary number of decorators
    to each callable member of a class
    '''
    def cls_decorator(cls):
        for name in cls.__dict__:
            if callable(getattr(cls, name)):
                for d in decs:
                    setattr(cls, name, d(getattr(cls, name)))
        return cls
    return cls_decorator
