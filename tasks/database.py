
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
                        ansi_move_cursor, format_file_size, fore_yellow
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
    temp_db_dump = conf_dir + '/database.sql'
    record_current = conf_dir + '/database.current'
    record_lastlocal = conf_dir + '/database.last-local'
    record_remote = conf_dir + '/database.remote'
    record_backup = conf_dir + '/database.backup'
    temp_db_backup = conf_dir + '/database.backup.sql'

    remote_checksum = '/database.{}.checksum.tsv'.format(kwargs['dbname'])
    remote_file = '/database.{}.sql'.format(kwargs['dbname'])

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

    def read_checksums(path: str):
        cont = ''
        if not os.path.exists(path): return False
        with open(path, 'r') as f:
            cont = f.read().replace('\n', '').replace('\r', '')
        
        arr = cont.split('\t')
        if len(arr) != 4: return False
        return (
            arr[0],          # hash summary
            int(arr[1]),     # size
            float(arr[2]),   # last modified time
            float(arr[3])    # last sync time
        )
    
    def write_checksums(dump: str, to_file: str):
        
        outs = False
        if os.path.exists(to_file): os.remove(to_file)
        with open(to_file, 'w') as f:
            file_stat = os.stat(dump)
            content = None
            md5 = hashlib.md5(b'').hexdigest()

            with open(dump, 'rb') as dumpfb:
                content = dumpfb.read()
                md5 = hashlib.md5(content).hexdigest()
            
            outs = [
                md5,
                file_stat.st_size,
                file_stat.st_mtime,
                time.time()
            ]

            f.write('{}\t{}\t{:.3f}\t{:.3f}'.format(
                md5, outs[1], outs[2], outs[3]
            ))

        return outs

    def push():

        dump_db(temp_db_dump)

        if not os.path.exists(temp_db_dump):
            error('the dump task failed. for {}'.format(temp_db_dump))

        c_current = write_checksums(temp_db_dump, record_current)
        if c_current == False:
            error('cannot generate local checksum.')
        
        c_hash, c_size, c_mtime, c_sync = c_current

        download_abs(remote_checksum, record_remote)
        if not os.path.exists(record_remote):
            
            # there is no remote checksum, the initial commit.
            upload_abs(temp_db_dump, remote_file)
            upload_abs(record_current, remote_checksum)

            if os.path.exists(record_lastlocal):
                os.remove(record_lastlocal)
            copy_local(record_current, record_lastlocal)
        
        else:

            c_remote = read_checksums(record_remote)
            if c_remote == False:
                error('invalid format of checksum file. {}'.format(record_remote))
            
            r_hash, r_size, r_mtime, r_sync = c_remote

            # there is no last-local file, indicating the local computer has
            # just initialized. conflict.
            has_conflict = False
            
            if not os.path.exists(record_lastlocal):
                has_conflict = True
            else:

                c_ll = read_checksums(record_lastlocal)
                if c_ll == False:
                    error('invalid format of checksum file. {}'.format(record_lastlocal))
                ll_hash, ll_size, ll_mtime, ll_sync = c_ll

                # if ll_hash == c_hash: 
                #     c_mtime = ll_mtime
                #     c_sync = ll_sync

                if r_sync > ll_sync: has_conflict = True
                else:

                    if r_hash == c_hash:

                        info('No change since last commit.')
                        pass  # identical

                    else:

                        # push
                        upload_abs(temp_db_dump, remote_file)
                        upload_abs(record_current, remote_checksum)

                        if os.path.exists(record_lastlocal):
                            os.remove(record_lastlocal)
                        copy_local(record_current, record_lastlocal)
            
            if has_conflict:
                if not os.path.exists(record_lastlocal):
                    warning('You have never pushed once on the local machine, yet the remote file')
                    warning('has already existed. You must ensure you\'d like to overwrite the remote.')
                    answ = input('Are you sure to overwrite remote database? [y/n] > ')

                    if answ == 'y':

                        # push
                        upload_abs(temp_db_dump, remote_file)
                        upload_abs(record_current, remote_checksum)

                        if os.path.exists(record_lastlocal):
                            os.remove(record_lastlocal)
                        copy_local(record_current, record_lastlocal)

                        info('You have overwritten the remote file.')
                    
                    else: info('Operation cancelled.')
                
                else:

                    warning('The remote file is newer than the local one.\n')
                    c_ll = read_checksums(record_lastlocal)
                    if c_ll == False:
                        error('invalid format of checksum file. {}'.format(record_lastlocal))
                
                    if c_ll[0] == c_hash: ll_hash, ll_size, ll_mtime, ll_sync = c_current
                    else: ll_hash, ll_size, ll_mtime, ll_sync = c_ll
                    
                    fore_red()
                    print('[l] {:<7}'.format(c_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(c_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(c_mtime))
                    ))

                    fore_green()
                    print('[r] {:<7}'.format(r_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(r_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(r_mtime))
                    ))

                    fore_yellow()
                    print('[p] {:<7}'.format(ll_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(ll_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(ll_mtime))
                    ))

                    answ = input('Are you sure to overwrite remote database? [y/n] > ')

                    if answ == 'y':

                        # push
                        upload_abs(temp_db_dump, remote_file)
                        upload_abs(record_current, remote_checksum)

                        if os.path.exists(record_lastlocal):
                            os.remove(record_lastlocal)
                        copy_local(record_current, record_lastlocal)

                        info('You have overwritten the remote file.')
                    
                    else: info('Operation cancelled.')

        if os.path.exists(temp_db_dump):
            os.remove(temp_db_dump)
        pass

    def fetch():
        
        download_abs(remote_checksum, record_remote)
        
        if not os.path.exists(record_remote):
            error('the remote is not initialized. you should push your initial commit first')
        c_remote = read_checksums(record_remote)
        if c_remote == False:
            error('invalid format for {}'.format(record_remote))
        r_hash, r_size, r_mtime, r_sync = c_remote
        
        # dump the local db.
        dump_db(temp_db_dump)

        c_current = write_checksums(temp_db_dump, record_current)
        if c_current == False:
            error('cannot generate local checksum.')
        c_hash, c_size, c_mtime, c_sync = c_current

        if c_hash == r_hash:

            info('Identical to remote.')
            if os.path.exists(record_lastlocal):
                os.remove(record_lastlocal)
            copy_local(record_remote, record_lastlocal)

        else:

            # no last sync on this machine.
            has_conflict = False
            if not os.path.exists(record_lastlocal):
                has_conflict = True
            
            else:

                c_ll = read_checksums(record_lastlocal)
                if c_ll == False:
                    error('invalid format of checksum file. {}'.format(record_lastlocal))
                ll_hash, ll_size, ll_mtime, ll_sync = c_ll

                if ll_sync < r_sync:
                    has_conflict = True

            warning('The following operation will drop your local copy of database, and will substitute')
            warning('with the remote one. This is dangerous and you are not able to recover from the')
            warning('replacement. We keep a backup of the current copy under *.backup.sql. Only the last')
            warning('activity can be reversed.')

            if has_conflict:
                warning('\nYou should pay extra attention, this operation contains merge conflict!')
            
            print('')

            if os.path.exists(record_lastlocal):
                c_ll = read_checksums(record_lastlocal)
                if c_ll == False:
                    error('invalid format of checksum file. {}'.format(record_lastlocal))
                
                ll_hash, ll_size, ll_mtime, ll_sync = c_ll

                fore_yellow()
                print('[p] {:<7}'.format(ll_hash[:7]), end = '')
                ansi_reset()
                print(' ({:>12}) {}'.format(
                    format_file_size(ll_size),
                    time.strftime('%Y-%m-%d %H:%M', time.localtime(ll_mtime))
                ))
   
            fore_red()
            print('[l] {:<7}'.format(c_hash[:7]), end = '')
            ansi_reset()
            print(' ({:>12}) {}'.format(
                format_file_size(c_size),
                time.strftime('%Y-%m-%d %H:%M', time.localtime(c_mtime))
            ))

            fore_green()
            print('[r] {:<7}'.format(r_hash[:7]), end = '')
            ansi_reset()
            print(' ({:>12}) {}'.format(
                format_file_size(r_size),
                time.strftime('%Y-%m-%d %H:%M', time.localtime(r_mtime))
            ))

            answ = input('\nAre you sure to drop and overwrite local database? [y/n] > ')

            if answ == 'y':
                
                if os.path.exists(record_lastlocal):
                    os.remove(record_lastlocal)
                copy_local(record_remote, record_lastlocal)

                if os.path.exists(temp_db_backup):
                    os.remove(temp_db_dump)
                copy_local(temp_db_dump, temp_db_backup)

                download_abs(remote_file, temp_db_dump)
                import_db(temp_db_dump)

                info('You have overwritten the local database.')
                    
            else: info('Operation cancelled.')

        if os.path.exists(temp_db_dump):
            os.remove(temp_db_dump)
        pass

    def diff():
        
        dump_db(temp_db_dump)

        if not os.path.exists(temp_db_dump):
            error('the dump task failed. for {}'.format(temp_db_dump))

        c_current = write_checksums(temp_db_dump, record_current)
        if c_current == False:
            error('cannot generate local checksum.')
        
        c_hash, c_size, c_mtime, c_sync = c_current

        download_abs(remote_checksum, record_remote)
        if not os.path.exists(record_remote):
            
            info('The remote repository is empty.')
        
        else:

            c_remote = read_checksums(record_remote)
            if c_remote == False:
                error('invalid format of checksum file. {}'.format(record_remote))
            
            r_hash, r_size, r_mtime, r_sync = c_remote

            # there is no last-local file, indicating the local computer has
            # just initialized. conflict.
            has_conflict = False
            
            if not os.path.exists(record_lastlocal):
                has_conflict = True
            else:

                c_ll = read_checksums(record_lastlocal)
                if c_ll == False:
                    error('invalid format of checksum file. {}'.format(record_lastlocal))
                
                ll_hash, ll_size, ll_mtime, ll_sync = c_ll
                if r_sync > ll_sync: has_conflict = True
                else:

                    if r_hash == c_hash:

                        info('No change since last commit.')
                        pass  # identical
                    
                    else:
                        
                        fore_green()
                        print('[l] {:<7}'.format(c_hash[:7]), end = '')
                        ansi_reset()
                        print(' ({:>12}) {}'.format(
                            format_file_size(c_size),
                            time.strftime('%Y-%m-%d %H:%M', time.localtime(c_mtime))
                        ))

                        fore_red()
                        print('[r] {:<7}'.format(r_hash[:7]), end = '')
                        ansi_reset()
                        print(' ({:>12}) {}'.format(
                            format_file_size(r_size),
                            time.strftime('%Y-%m-%d %H:%M', time.localtime(r_mtime))
                        ))
            
            if has_conflict:
                if not os.path.exists(record_lastlocal):
                    warning('You have never pushed once on the local machine, yet the remote file')
                    warning('has already existed. You must ensure you\'d like to overwrite the remote.')
                
                else:
                    
                    warning('The remote file is newer than the local one.\n')
                    c_ll = read_checksums(record_lastlocal)
                    if c_ll == False:
                        error('invalid format of checksum file. {}'.format(record_lastlocal))
                
                    ll_hash, ll_size, ll_mtime, ll_sync = c_ll
                    
                    fore_red()
                    print('[l] {:<7}'.format(c_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(c_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(c_mtime))
                    ))

                    fore_green()
                    print('[r] {:<7}'.format(r_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(r_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(r_mtime))
                    ))

                    fore_yellow()
                    print('[p] {:<7}'.format(ll_hash[:7]), end = '')
                    ansi_reset()
                    print(' ({:>12}) {}'.format(
                        format_file_size(ll_size),
                        time.strftime('%Y-%m-%d %H:%M', time.localtime(ll_mtime))
                    ))

        if os.path.exists(temp_db_dump):
            os.remove(temp_db_dump)
        pass

    return {
        'fetch': fetch,
        'push': push,
        'diff': diff
    }