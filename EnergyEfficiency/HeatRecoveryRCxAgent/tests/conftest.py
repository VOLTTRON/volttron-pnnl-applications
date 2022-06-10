import os
import sys


def path_is_in_pythonpath(path):
    path = os.path.normcase(path)
    return any(os.path.normcase(sp) == path for sp in sys.path)


module_dir = os.path.realpath(os.path.dirname(__file__))

if not path_is_in_pythonpath(module_dir):
    sys.path.insert(0, module_dir)

