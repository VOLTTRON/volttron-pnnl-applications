# fn_decs.py
import time
import logging
from functools import wraps

def timer(fn):
    '''
    Prints execution time of decorated function
    '''
    @wraps(fn)
    def g(*args, **kwargs):
        now = time.time()
        res = fn(*args, **kwargs)
        print 'Function ', fn.__name__, 'took', (time.time()-now), 'ms'
        return res
    return g
