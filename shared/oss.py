
# ./shared/oss.py
#   oss upload and download support. provide a interface for oss access.
#   every interface must implement get_required_args and init function.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import os
import types
import copy

from shared.configuration import get_providers, load_provider, remove_duplicate
from shared.ansi import error

required_args = [
    'dest'      # the local destination folder (the one to sync)
]

def get_provider(app, provider) -> types.ModuleType:
    provs = get_providers(app, 'oss')
    
    if provider in provs:
        return load_provider(app, 'oss', provider)
    
    else:
        error('the provider {0}_{1} not found.'.format(
            'oss', provider
        ))
        exit(0)

def get_required_args(app, provider) -> list:
    mod = get_provider(app, provider)
    return remove_duplicate(required_args + mod.required_args)

# the init function returns a dictionary of interface function. for oss, the
# interface is like:
#
#   download-abs: (str, str) -> str
#   download-rel: (str, str) -> str
#   upload-abs: (str, str) -> int
#   upload-rel: (str, str) -> int
#   move-remote: (str, str) -> int

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

    kwargs['config-file'] = conf_dir + '/oss.config'
    
    if os.path.exists(kwargs['config-file']):
        os.remove(kwargs['config-file'])
    
    prov = get_provider(app, provider)

    # initialize the oss provider.
    prov.init(kwargs)
    
    func_dict = {}

    def download_file(remote: str, local: str) -> str:
        return prov.download_file(remote, local, kwargs)
    
    def upload_file(local: str, remote: str) -> int:
        return prov.upload_file(local, remote, kwargs)
    
    def download_relative(remote: str, relative: str) -> str:
        prov.download_file(remote, kwargs['dest'].replace('\\','/') + relative, kwargs)
        return '.{0}'.format(relative)
    
    def upload_relative(relative: str, remote: str) -> int:
        return prov.upload_file(kwargs['dest'].replace('\\','/') + relative, remote, kwargs)
    
    def remote_move(src: str, dest: str) -> int:
        return prov.move_file(src, dest, kwargs)
    
    def remote_copy(src: str, dest: str) -> int:
        return prov.copy_file(src, dest, kwargs)
    
    func_dict['download-abs'] = download_file
    func_dict['download-rel'] = download_relative
    func_dict['upload-abs'] = upload_file
    func_dict['upload-rel'] = upload_relative
    func_dict['remote-move'] = remote_move
    func_dict['remote-copy'] = remote_copy

    return func_dict