
# ./shared/db.py
#   dump the database to a file, and loads the dump to create a database.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import os
import types
import copy

from shared.configuration import get_providers, load_provider, remove_duplicate
from shared.ansi import error

required_args = [
    'dbname',     # the database to import/export.
]

def get_provider(app, provider) -> types.ModuleType:
    provs = get_providers(app, 'db')
    
    if provider in provs:
        return load_provider(app, 'db', provider)
    
    else:
        error('the provider {0}_{1} not found.'.format(
            'db', provider
        ))
        exit(0)

def get_required_args(app, provider) -> list:
    mod = get_provider(app, provider)
    return remove_duplicate(required_args + mod.required_args)

# the init function returns a dictionary of interface function. for oss, the
# interface is like:
#
#   dump(dump: str) -> None
#   import(dump: str) -> None 

def init(app, provider, kwargs):

    # make a deep copy and avoid changing the default configuration.
    kwargs = copy.deepcopy(kwargs)

    # aliasing the private fields.
    kwargs['app'] = app

    task_name = kwargs['_name'].replace('/', "_").replace('\\', "_") \
                               .replace(':', "_").replace('*', "_") \
                               .replace('?', "_").replace('|', "_") \
                               .replace('<', "_").replace('>', "_") \
                               .replace('"', "_")
    conf_dir = app + '/conf/{0}'.format(task_name)

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)

    prov = get_provider(app, provider)

    # initialize the oss provider.
    prov.init(kwargs)
    
    func_dict = {}

    def dump_database(dump: str) -> None:
        return prov.dump_database(dump, kwargs)
    
    def import_database(dump: str) -> int:
        return prov.import_database(dump, kwargs)
    
    func_dict['dump'] = dump_database
    func_dict['import'] = import_database

    return func_dict