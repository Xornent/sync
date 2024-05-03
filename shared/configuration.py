
# ./shared/configuration.py
#   utility functions to access the application configurations.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import importlib
import importlib.machinery
import importlib.util
import types
from shared.ansi import error, warning, info

def import_spec(spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def remove_empty(ls_str: list) -> list:
    while '' in ls_str:
        ls_str.remove('')
    return ls_str

def remove_duplicate(ls_str: list) -> list:
    return list(set(ls_str))

# return the list of providers (strings) for the specified interface.
# meanwhile, this method checks the interface is available.
def get_providers(appdir: str, interface:str) -> list:

    provs = []

    for line in open(appdir + '/conf/providers', 'r'):
        line = line.replace('\r', '').replace('\n', '')
        if line == '': continue
        if line.startswith('#'): continue

        if not ('\t' in line):
            error('invalid /conf/providers format: `{0}`. each line of valid ' +
                  'providers should be tab-limited. (interface \\t impl'.format(line))
            exit(1)
        
        splits = remove_empty(line.split('\t'))
        if len(splits) != 2:
            error('invalid /conf/providers format: `{0}` should be two elements, ' +
                  'interface and implementation names.'.format(line))
            exit(1)
        
        spec = importlib.util.find_spec('shared.{0}'.format(splits[0]))
        if spec is None:
            error('cannot find interface module {0}'.format(
                'shared.{0}'.format(splits[0])
            ))
            exit(1)
        
        if splits[0] == interface:
            provs += [splits[1]]
    
    return provs

def load_provider(appdir: str, interface: str, impl: str) -> types.ModuleType:
    spec = importlib.util.find_spec('shared.{0}_{1}'.format(interface, impl))
    if spec is None:
        error('cannot find implementation module {0}'.format(
            'shared.{0}_{1}'.format(interface, impl)
        ))
        exit(1)
    
    else: return import_spec(spec)

# return the list of interfaces (strings) for the specified task.
# meanwhile, this method checks the task is available.
def get_interfaces(appdir: str, task:str) -> list:

    provs = []

    for line in open(appdir + '/conf/tasks', 'r'):
        line = line.replace('\r', '').replace('\n', '')
        if line == '': continue
        if line.startswith('#'): continue

        if not ('\t' in line):
            error(('invalid /conf/tasks format: `{0}`. each line of valid ' +
                  'providers should be tab-limited.').format(line))
            exit(1)
        
        splits = remove_empty(line.split('\t'))
        if len(splits) < 2:
            error('invalid /conf/tasks format: `{0}` should have at least 2 elements.'.format(line))
            exit(1)
        
        spec = importlib.util.find_spec('tasks.{0}'.format(splits[0]))
        if spec is None:
            error('cannot find task module {0}'.format(
                'tasks.{0}'.format(splits[0])
            ))
            exit(1)
        
        if splits[0] == task:
            provs += splits[1:]
    
    return provs

def load_interface(appdir: str, interface: str) -> types.ModuleType:
    spec = importlib.util.find_spec('shared.{0}'.format(interface))
    if spec is None:
        error('cannot find interface module {0}'.format(
            'shared.{0}'.format(interface)
        ))
        exit(1)
    
    else: return import_spec(spec)

def get_tasks(appdir: str) -> list:
    
    tasks = []
    for line in open(appdir + '/conf/tasks', 'r'):
        line = line.replace('\r', '').replace('\n', '')
        if line == '': continue
        if line.startswith('#'): continue

        if not ('\t' in line):
            error(('invalid /conf/tasks format: `{0}`. each line of valid ' +
                  'providers should be tab-limited.').format(line))
            exit(1)
        
        splits = remove_empty(line.split('\t'))
        if len(splits) < 2:
            error('invalid /conf/tasks format: `{0}` should have at least 2 elements.'.format(line))
            exit(1)
        
        spec = importlib.util.find_spec('tasks.{0}'.format(splits[0]))
        if spec is None:
            error('cannot find task module {0}'.format(
                'tasks.{0}'.format(splits[0])
            ))
            exit(1)
        
        tasks += [splits[0]]
    
    return tasks

def load_task(appdir: str, task: str) -> types.ModuleType:
    spec = importlib.util.find_spec('tasks.{0}'.format(task))
    if spec is None:
        error('cannot find interface module {0}'.format(
            'tasks.{0}'.format(task)
        ))
        exit(1)
    
    else: return import_spec(spec)