
# ./tasks/database.py
#   the sync task to sync database dumps
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import copy
import os
import time
import hashlib

from shared.configuration import get_interfaces, load_interface, remove_duplicate
from shared.ansi import error, print_message, warning, info, line_start, fill_blank, \
                        common_length, fore_green, fore_red, ansi_reset, \
                        ansi_move_cursor
from shared.local import move_local, copy_local
from shared.getch import getch

required_args = [
    'dbname',
    'y'
]

def get_required_interfaces(app):
    # for every registered interface, there need to be one provider selected.
    interfaces = get_interfaces(app, 'database')
    args = [(x + '-provider') for x in interfaces]
    return args

def get_required_args(app, providers: dict):
    args = copy.deepcopy(required_args)
    
    for intf in get_interfaces(app, 'database'):
        mod = load_interface(app, intf)
        iarg = mod.get_required_args(app, providers[intf + '-provider'])
        args += iarg
    
    return remove_duplicate(args)

def init(app, providers: dict, kwargs: dict):

    intfs = {}
    for intf in get_interfaces(app, 'database'):
        mod = load_interface(app, intf)
        methods = mod.init(app, providers[intf + '-provider'], kwargs)
        intfs[intf] = methods
    
    task_name = kwargs['_name'].replace('/', "_").replace('\\', "_") \
                               .replace(':', "_").replace('*', "_") \
                               .replace('?', "_").replace('|', "_") \
                               .replace('<', "_").replace('>', "_") \
                               .replace('"', "_")
    
    conf_dir = app + '/conf/{0}'.format(task_name)
    temp_db_dump = conf_dir + '/database.current'
    temp_db_backup = conf_dir + '/database.backup'

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)
    
    download_abs = intfs['oss']['download-abs']
    download_rel = intfs['oss']['download-rel']
    upload_abs = intfs['oss']['upload-abs']
    upload_rel = intfs['oss']['upload-rel']
    move_remote = intfs['oss']['remote-move']
    copy_remote = intfs['oss']['remote-copy']
    dump_db = intfs['db']['dump']
    import_db = intfs['db']['import']

    def push():
        pass

    def fetch():
        pass

    def diff():
        pass

    return {
        'fetch': fetch,
        'push': push,
        'diff': diff
    }