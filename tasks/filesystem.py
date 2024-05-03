
# ./tasks/file_system.py
#   the sync task to sync local and remote file systems.
#
#   tasks can make use of one or more interface providers, and utilize the 
#   functions that the interface provides, for example, the `oss` interface.
#   the linkage of what interface a task can have access is declared in the
#   /conf/tasks file as a tab-delimited sequence.
#
#   every sync task must implement the following sync utility functions:
#   fetch, push, diff, init, get_required_interfaces and get_required_args.
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
    'dest',
    'y'
]

def get_required_interfaces(app):
    # for every registered interface, there need to be one provider selected.
    interfaces = get_interfaces(app, 'filesystem')
    args = [(x + '-provider') for x in interfaces]
    return args

def get_required_args(app, providers: dict):
    args = copy.deepcopy(required_args)
    
    for intf in get_interfaces(app, 'filesystem'):
        mod = load_interface(app, intf)
        iarg = mod.get_required_args(app, providers[intf + '-provider'])
        args += iarg
    
    return remove_duplicate(args)

def init(app, providers: dict, kwargs: dict):

    intfs = {}
    for intf in get_interfaces(app, 'filesystem'):
        mod = load_interface(app, intf)
        methods = mod.init(app, providers[intf + '-provider'], kwargs)
        intfs[intf] = methods
    
    # here, file system is relied on the 'oss' interface only, providing
    #   download-abs: (str, str) -> str
    #   download-rel: (str, str) -> str
    #   upload-abs: (str, str) -> str
    #   upload-rel: (str, str) -> str
    
    conf_dir = app + '/conf'
    remote_chksum = conf_dir + '/filesystem.remote'
    current_chksum = conf_dir + '/filesystem.current'
    last_local_chksum = conf_dir + '/filesystem.last-local'

    download_abs = intfs['oss']['download-abs']
    download_rel = intfs['oss']['download-rel']
    upload_abs = intfs['oss']['upload-abs']
    upload_rel = intfs['oss']['upload-rel']
    move_remote = intfs['oss']['remote-move']
    copy_remote = intfs['oss']['remote-copy']

    manual_zero_md5 = 'd41d8cd98f00b204e9800998ecf8427e'

    # try to get the remote checksum file. and returns a list of recorded columns
    # in the parsed checksum.
    #
    # if there is a network issue, or the remote repository has not yet been 
    # initialized, or any other reason that the download failed. we assume that
    # the remote is empty and returns an empty but valid parse result.

    def read_remote_checksum():

        if (os.path.exists(remote_chksum)):
            os.remove(remote_chksum)

        tsv = download_abs('/filesystem.checksum.tsv', remote_chksum)

        if not os.path.exists(remote_chksum):
            return [], [], [], [], []

        fp = open(remote_chksum, 'r', encoding = 'utf-8')
        content = fp.read().splitlines()

        hash_num = []
        file_length = []
        last_modified = []
        last_sync = []
        file_path = []

        for line in content:
            ihash, ilen, mtime, stime, ipath = line.split('\t')
            hash_num += [ihash]
            file_length += [int(ilen)]
            last_modified += [float(mtime)]
            last_sync += [float(stime)]
            file_path += [ipath]

        return hash_num, file_length, last_modified, last_sync, file_path

    # get the current checksum. if there is not any, returns an empty set.
    # this method SHOULD ONLY BE CALLED from build_local_checksum()

    # read from 'filesystem.last-local'

    def read_local_last_checksum():

        if not os.path.exists(last_local_chksum):
            return [], [], [], [], []

        fp = open(last_local_chksum, 'r', encoding = 'utf-8')
        content = fp.read().splitlines()

        hash_num = []
        file_length = []
        last_modified = []
        last_sync = []
        file_path = []

        for line in content:
            ihash, ilen, mtime, stime, ipath = line.split('\t')
            hash_num += [ihash]
            file_length += [int(ilen)]
            last_modified += [float(mtime)]
            last_sync += [float(stime)]
            file_path += [ipath]

        return hash_num, file_length, last_modified, last_sync, file_path
    
    # build the local file index dictionary and calculate the hash numbers
    # it do not require there is a local checksum already, it tries to read the
    # local checksum first simply because it want to detect which files are
    # not changed and saves time for not calculating the unchanged hash.

    # build to 'filesystem.current'. this file should be copied to '.last-local'
    # only after a success push.

    def build_local_checksum():

        local_h, local_l, local_t, local_st, local_p = read_local_last_checksum()
        info('Building local hash checksums ...')

        last_modified = []
        file_length = []
        file_name = []
        hash_num = []
        gen_time = []
        file_path = []

        lines = []

        ignore_marks = []
        sync_dir = kwargs['dest']

        for root, _, files in os.walk(sync_dir, topdown = True):

            if '.ignore' in files:
                ignore_marks += [root.replace(sync_dir, '').replace('\\', '/')]

            # since we turn the top-down on, the parent directory is always before
            # its children, so we any descendents will simply be ignored
            
            is_ignored = False
            for ignores in ignore_marks:
                if root.replace(sync_dir, '').replace('\\', '/').startswith(ignores):
                    is_ignored = True
            
            if is_ignored: continue

            for file in files:

                absolute_path = os.path.join(root, file)
                relative_path = absolute_path.replace(sync_dir, '').replace('\\', '/')
                file_path += [relative_path]
                file_name += [file]

                file_stat = os.stat(absolute_path)

                tm_last = file_stat.st_mtime
                last_modified += [tm_last]
                
                leng = file_stat.st_size
                file_length += [leng]

                current_time = time.time()
                
                line_start()
                fill_blank(80, relative_path)

                # if exactly the same, we assume it, and skip reading the file 
                # content for calculations of md5. since most files do not change.

                if relative_path in local_p:
                    index = local_p.index(relative_path)

                    if tm_last == local_t[index] and \
                       leng == local_l[index]:

                        hash_num += [local_h[index]]
                        gen_time += [local_st[index]]

                        lines += ['{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                            local_h[index], 
                            local_l[index], 
                            tm_last, 
                            local_st[index], 
                            relative_path
                        )]

                        continue
                    
                # calculate content md5 identifier and file content length as the
                # unique identifier for the file

                fp = open(absolute_path, 'rb')
                md5x = ''
                fp.seek(0)

                # for files < 10M, it would be better to digest it all.
                if leng < 1024 * 1024 * 10:
                    content = fp.read()
                    md5x = hashlib.md5(content).hexdigest()

                else:
                    for x in range(leng // (1024 * 1024)):
                        fp.seek(x * 1024 * 1024)
                        content = fp.read(1024 * 1024) # strictly by v7.
                        md5x += hashlib.md5(content).hexdigest()
                    
                    # the last section smaller than 1 MiB.

                    fp.seek((leng // (1024 * 1024)) * 1024 * 1024)
                    content = fp.read()
                    md5x += hashlib.md5(content).hexdigest()

                    md5x = hashlib.md5(md5x.encode('utf-8')).hexdigest()

                hash_num += [md5x]
                gen_time += [current_time]
                fp.close()

                lines += ['{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                    md5x, leng, tm_last, current_time, relative_path
                )]

        for ignore_dir in ignore_marks:
            
            file_path += [ignore_dir + '/.ignore']
            file_name += ['.ignore']
            hash_num += [manual_zero_md5]
            last_modified += [0.0]
            file_length += [0]

            if (ignore_dir + '/.ignore') in local_p:
                index = local_p.index(ignore_dir + '/.ignore')
                
                gen_time += [local_st[index]]

                lines += ['{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                    local_h[index], 
                    local_l[index], 
                    0.0, 
                    local_st[index], 
                    ignore_dir + '/.ignore'
                )]

                continue

            
            current_time = time.time()
            gen_time += [current_time]

            lines += ['{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                manual_zero_md5, 0, 0.0, current_time,
                ignore_dir + '/.ignore'
            )]

        print('')
        fill_blank(100, 'Sync checksum built.')
        print('')

        if (os.path.exists(current_chksum)):
            os.remove(current_chksum)

        checksum = open(current_chksum, 'a', encoding = 'utf-8')
        checksum.writelines(lines)
        checksum.close()

        return hash_num, file_length, last_modified, gen_time, file_path

    def push():

        l_hash_num, l_file_length, l_last_modified, l_stime, l_file_path = \
            build_local_checksum()
        ll_hash_num, ll_file_length, ll_last_modified, ll_stime, ll_file_path = \
            read_local_last_checksum()
        r_hash_num, r_file_length, r_last_modified, r_stime, r_file_path = \
            read_remote_checksum()
        
        actual_checksum = []

        # we do not remove files on the cloud if the local corresponded delete it,
        # only to update the checksum file category and to inform the updater not
        # to sync it the next time. it remains on cloud however.

        # so the update table is:
        #
        #   local     remote    changed   op.
        #   +         +         +         copy
        #   +         +         -         -
        #   +         -         auto      copy
        #   -         +         deleted   -

        overview_uploads = []
        overview_modified = []
        overview_removed = []

        confirm_synccfl = []
        confirm_remote_move = []
        confirm_remote_copy = []
        
        num_unchanged = 0

        print('')

        for x in range(len(l_file_path)):
            local_file = l_file_path[x]
            local_line = '{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                l_hash_num[x], l_file_length[x], l_last_modified[x], 
                l_stime[x], local_file )
            
            if local_file in r_file_path:
                rx = r_file_path.index(local_file)
                remote_line = '{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                    r_hash_num[rx], r_file_length[rx], r_last_modified[rx], 
                    r_stime[rx], local_file )

                # if the file with changed length or hash number, it is say to 
                # be a new file. we should then compare the sync time. if the
                # local sync time is newer than the remote, it is safe to be
                # pushed, otherwise, this means local file has push conflicts.

                is_updated = (r_hash_num[rx] != l_hash_num[x]) or \
                             (r_file_length[rx] != l_file_length[x])
                
                is_newer = False
                if local_file in ll_file_path:
                    llx = ll_file_path.index(local_file)
                    is_newer = r_stime[rx] > ll_stime[llx]
                
                # the file does not exist in the last sync. it must be created at
                # local after the sync. however, there is a remote one indicating
                # the remote must be newer, this should be a conflct.
                else: is_newer = True

                if is_updated:

                    if not is_newer:
                        overview_modified += \
                            [print_message('\033[1;33m', '~', local_file)]
                        upload_rel(local_file, local_file)
                        actual_checksum += [local_line]

                    else: confirm_synccfl += [(local_file, l_last_modified[x],
                                               r_last_modified[rx], local_line, 
                                               remote_line, False)]

                else: 
                    num_unchanged += 1
                    actual_checksum += [local_line]

            else:

                # there is an remote identity to the attempt-to-upload file.
                if l_hash_num[x] in r_hash_num and l_hash_num[x] != manual_zero_md5:
                    remotex = r_hash_num.index(l_hash_num[x])

                    # represent that you have moved a local file and sync.
                    if not r_file_path[remotex] in l_file_path:

                        # the local hash num exists in remote. but the new local 
                        # file did not. this indicates a move of remote files. 
                        # but the hash num can match accidentally, so we ask the user.

                        confirm_remote_move += [(r_file_path[remotex], local_file, 
                                                 local_line, True)]

                    else: # represent you have made a duplicate of a local file.

                        confirm_remote_copy += [(r_file_path[remotex], local_file, 
                                                 local_line, True)]

                else: # simple upload

                    overview_uploads += \
                        [print_message('\033[1;32m', '+', local_file)]
                    upload_rel(local_file, local_file)
                    actual_checksum += [local_line]

        for x in range(len(r_file_path)):
            remote_file = r_file_path[x]

            if not remote_file in l_file_path:
                overview_removed += [print_message('\033[1;31m', '-', remote_file)]

        if len(overview_uploads) + len(overview_modified) > 0:
            print('\n')

        # here, we will handle the user confirmation using cli.

        info('You will manually specify behaviors for the following files:')
        info('<x> for selection, <space> for de-selection, <j>/<k> to move up and down. \n')

        warning('These files have merge conflicts (remote updated since last sync):')
        info('place <x> when you would like to over-write the remote file with the local version')
        info('place <space> if you want to keep the remote and local files unchanged \n')

        choice = []
        for local_file, ltime, rtime, lline, rline, deflt in confirm_synccfl:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            local = time.strftime('%Y-%m-%d %H:%M', time.localtime(ltime))
            remote = time.strftime('%Y-%m-%d %H:%M', time.localtime(rtime))
            fore_red()
            print('[l]', common_length(local, 16), end = ' ')
            fore_green()
            print('[r]', common_length(remote, 16), end = ' ')
            ansi_reset()
            print(common_length(local_file, 70))
            choice += [deflt]
        
        choice = edit_lines(choice)

        ind = 0
        for local_file, ltime, rtime, lline, rline, _ in confirm_synccfl:
            action = choice[ind]

            if action:
                overview_modified += \
                    [print_message('\033[1;33m', '~', local_file)]
                upload_rel(local_file, local_file)
                actual_checksum += [lline]
            
            else: actual_checksum += [rline]
            
            ind += 1

        warning('We detected that you move or copy local files since last sync:')
        info('place <x> to perform copy or move remotely (saves network volume)')
        info('place <space> if you insist on uploading another copy from local \n')

        choice_move = []
        for remote_file, local_file, lline, deflt in confirm_remote_move:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            fore_red()
            print('[v]', end = ' ')
            fore_green()
            print('[from]', end = ' ')
            ansi_reset()
            print(common_length(remote_file, 40), end = ' ')
            fore_green()
            print('[to]', end = ' ')
            ansi_reset()
            print(common_length(local_file, 40))
            choice_move += [deflt]

        choice_move = edit_lines(choice_move)
        
        ind = 0
        for remote_file, local_file, lline, deflt in confirm_remote_move:
            action = choice_move[ind]

            if action:
                overview_uploads += \
                    [print_message('\033[1;33m', 'v', local_file)]
                move_remote(remote_file, local_file)
                actual_checksum += [lline]
            
            else: 
                overview_uploads += \
                    [print_message('\033[1;33m', '+', local_file)]
                upload_rel(local_file, local_file)
                actual_checksum += [lline]
            
            ind += 1

        print('')
        
        choice_cp = []
        for remote_file, local_file, lline, deflt in confirm_remote_copy:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            fore_red()
            print('[c]', end = ' ')
            fore_green()
            print('[from]', end = ' ')
            ansi_reset()
            print(common_length(remote_file, 40), end = ' ')
            fore_green()
            print('[to]', end = ' ')
            ansi_reset()
            print(common_length(local_file, 40))
            choice_cp += [deflt]

        choice_cp = edit_lines(choice_cp)
        
        ind = 0
        for remote_file, local_file, lline, deflt in confirm_remote_copy:
            action = choice_cp[ind]

            if action:
                overview_uploads += \
                    [print_message('\033[1;33m', 'c', local_file)]
                copy_remote(remote_file, local_file)
                actual_checksum += [lline]
            
            else: 
                overview_uploads += \
                    [print_message('\033[1;33m', '+', local_file)]
                upload_rel(local_file, local_file)
                actual_checksum += [lline]
            
            ind += 1

        print('{:<80}'.format('Upload files finished.'))

        print('\n\033[1;32m{0} files uploaded.\033[0m'
              .format(str(len(overview_uploads))))
        for x in overview_uploads: print(x)

        print('\n\033[1;33m{0} files modified.\033[0m'
              .format(str(len(overview_modified))))
        for x in overview_modified: print(x)

        print('\n\033[1;31m{0} files removed compared with remote.\033[0m'
              .format(str(len(overview_removed))))
        for x in overview_removed: print(x)

        print('\n\033[1;30m{0} files unchanged. ({1} local)\033[0m'
              .format( num_unchanged, len(l_file_path)))

        print('')

        print('\033[1;32m{0}\033[0m'
              .format( 'Uploading updated file catalog checksums ...' ))
        if (os.path.exists(last_local_chksum)):
            os.remove(last_local_chksum)

        checksum = open(last_local_chksum, 'a', encoding = 'utf-8')
        checksum.writelines(actual_checksum)
        checksum.close()
        upload_abs(last_local_chksum, '/filesystem.checksum.tsv')

        print('\n\033[1;32m{0}\033[0m'
              .format( 'All jobs finished.' ))

    def edit_lines(choice):
        n_choices = len(choice)
        ansi_move_cursor(-n_choices, 1)
        current_line = 0

        while current_line < n_choices:
            key = getch().get_value()
    
            if key == b'x':
                fill_blank(1, 'x')
                ansi_move_cursor(1, -1)
                choice[current_line] = True
                current_line += 1
            elif key == b' ':
                fill_blank(1, ' ')
                ansi_move_cursor(1, -1)
                choice[current_line] = False
                current_line += 1
            elif key == b'j':
                ansi_move_cursor(1, 0)
                current_line += 1
            elif key == b'k' and current_line > 0:
                ansi_move_cursor(-1, 0)
                current_line -= 1
        
        ansi_move_cursor(0, -1)
        return choice

    def fetch():

        l_hash_num, l_file_length, l_last_modified, l_stime, l_file_path = \
            build_local_checksum()
        ll_hash_num, ll_file_length, ll_last_modified, ll_stime, ll_file_path = \
            read_local_last_checksum()
        r_hash_num, r_file_length, r_last_modified, r_stime, r_file_path = \
            read_remote_checksum()
        
        actual_checksum = []

        overview_downloads = []
        overview_modified = []
        overview_removed = []
        num_unchanged = 0
        sync_dir = kwargs['dest']

        confirm_synccfl = []
        confirm_local_move = []
        confirm_local_copy = []
        
        for x in range(len(l_file_path)):
            local_file = l_file_path[x]

            if not local_file in r_file_path:
                overview_removed += [local_file]

        print('')

        for x in range(len(r_file_path)):
            remote_file = r_file_path[x]
            remote_line = '{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                r_hash_num[x], r_file_length[x], r_last_modified[x], 
                r_stime[x], remote_file )
            
            if remote_file in l_file_path:
                lx = l_file_path.index(remote_file)
                local_line = '{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                    l_hash_num[lx], l_file_length[lx], l_last_modified[lx], 
                    l_stime[lx], remote_file )

                # the newer condition
                is_updated = (r_hash_num[x] != l_hash_num[lx]) or \
                             (r_file_length[x] != l_file_length[lx])
                
                is_newer = False
                if remote_file in ll_file_path:
                    llx = ll_file_path.index(remote_file)
                    is_newer = r_stime[x] > ll_stime[llx]
                
                else: is_newer = True

                if is_updated:

                    if not is_newer:
                        overview_modified += [print_message('\033[1;33m', '~', remote_file)]
                        download_rel(remote_file, remote_file)
                        os.utime(kwargs['dest'] + remote_file, (time.time(), r_last_modified[x]))
                        actual_checksum += [remote_line]
                    
                    else: confirm_synccfl += [(remote_file, l_last_modified[lx],
                                               r_last_modified[x], local_line, 
                                               remote_line, False)]

                else: 
                    num_unchanged += 1
                    actual_checksum += [remote_line]
                    os.utime(kwargs['dest'] + remote_file, (time.time(), r_last_modified[x]))

            else:

                if r_hash_num[x] in l_hash_num and r_hash_num[x] != manual_zero_md5:
                    localx = l_hash_num.index(r_hash_num[x])
                    if not l_file_path[localx] in r_file_path:

                        # the new remote file has an existing hash num at other place in the local
                        confirm_local_move += [(l_file_path[localx], remote_file, 
                                                remote_line, True, r_last_modified[x])]
                        overview_removed -= [l_file_path[localx]]

                    else:
                        confirm_local_copy += [(l_file_path[localx], remote_file, 
                                                remote_line, True, r_last_modified[x])]

                else: 
                    overview_downloads += [print_message('\033[1;32m', '+', remote_file)]
                    download_rel(remote_file)
                    os.utime(kwargs['dest'] + remote_file, (time.time(), r_last_modified[x]))
                    actual_checksum += [remote_line]

        if len(overview_downloads) + len(overview_modified) > 0:
            print('\n')
        
        # here, we will handle the user confirmation using cli. ---------------

        if  len(confirm_synccfl) > 0 or \
            len(confirm_local_copy) > 0 or \
            len(confirm_local_move) > 0 or \
            len(overview_removed) > 0:
            info('You will manually specify behaviors for the following files:')
            info('<x> for selection, <space> for de-selection, <j>/<k> to move up and down. \n')

        if len(confirm_synccfl) > 0:
            warning('These files have merge conflicts (remote updated since last sync):')
            info('place <x> when you would like to over-write the remote file with the local one')
            info('place <space> if you want to keep the remote and local files unchanged \n')

        choice = []
        for local_file, ltime, rtime, lline, rline, deflt in confirm_synccfl:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            local = time.strftime('%Y-%m-%d %H:%M', time.localtime(ltime))
            remote = time.strftime('%Y-%m-%d %H:%M', time.localtime(rtime))
            fore_red()
            print('[l]', common_length(local, 16), end = ' ')
            fore_green()
            print('[r]', common_length(remote, 16), end = ' ')
            ansi_reset()
            print(common_length(local_file, 70))
            choice += [deflt]
        
        choice = edit_lines(choice)

        ind = 0
        for local_file, ltime, rtime, lline, rline, _ in confirm_synccfl:
            action = choice[ind]

            if action:
                overview_modified += \
                    [print_message('\033[1;33m', '~', local_file)]
                download_rel(local_file, local_file)
                actual_checksum += [rline]
                os.utime(sync_dir + local_file, (time.time(), rtime))
            
            else: actual_checksum += [lline]
            
            ind += 1

        if len(confirm_synccfl) > 0:
            print('\n')

        if len(confirm_local_move) > 0:
            warning('We detected that you move or copy remote files since last sync:')
            info('place <x> to perform copy or move locally (saves network volume)')
            info('place <space> if you insist on uploading another download from remote \n')

        choice_move = []
        for old, new, lline, deflt, _ in confirm_local_move:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            fore_red()
            print('[v]', end = ' ')
            fore_green()
            print('[from]', end = ' ')
            ansi_reset()
            print(common_length(old, 40), end = ' ')
            fore_green()
            print('[to]', end = ' ')
            ansi_reset()
            print(common_length(new, 40))
            choice_move += [deflt]

        choice_move = edit_lines(choice_move)
        
        ind = 0
        for old, new, rline, deflt, rtime in confirm_local_move:
            action = choice_move[ind]

            if action:
                overview_downloads += \
                    [print_message('\033[1;33m', 'v', new)]
                move_local(sync_dir + old, sync_dir + new)
                actual_checksum += [rline]
            
            else: 
                overview_downloads += \
                    [print_message('\033[1;33m', '+', new)]
                download_rel(new, new)
                actual_checksum += [rline]

            os.utime(sync_dir + new, (time.time(), rtime))
            
            ind += 1

        if len(confirm_local_move) > 0:
            print('')
            print('')
        
        choice_cp = []
        for old, new, rline, deflt, _ in confirm_local_copy:
            print('[{0}] '.format('x' if deflt else ' '), end = '')
            fore_red()
            print('[c]', end = ' ')
            fore_green()
            print('[from]', end = ' ')
            ansi_reset()
            print(common_length(old, 40), end = ' ')
            fore_green()
            print('[to]', end = ' ')
            ansi_reset()
            print(common_length(new, 40))
            choice_cp += [deflt]

        choice_cp = edit_lines(choice_cp)
        
        ind = 0
        for old, new, rline, deflt, rtime in confirm_local_copy:
            action = choice_cp[ind]

            if action:
                overview_downloads += \
                    [print_message('\033[1;33m', 'c', new)]
                copy_local(sync_dir + old, sync_dir + new)
                actual_checksum += [rline]
            
            else: 
                overview_downloads += \
                    [print_message('\033[1;33m', '+', local_file)]
                download_rel(new, new)
                actual_checksum += [rline]
            
            os.utime(sync_dir + new, (time.time(), rtime))
            ind += 1

        if len(confirm_local_copy) > 0:
            print('')
            
        # local deletion ------------------------------------------------------

        if len(overview_removed) > 0:
            print('\033[1;31m{0} files removed compared with remote.\033[0m'
                  .format(str(len(overview_removed))))
        
            warning('These files has been deleted remotely since last sync, do you want to \n' +
                    'remove them from your local machine? This operation cannot be reversed!')
            info('place <x> to delete from local machine')
            info('place <space> to keep the local copy, you can push them back to remote later\n')

        choice_rm = []
        for x in overview_removed:
            print('[ ] ', end = '')
            fore_red()
            print('[-]', end = ' ')
            ansi_reset()
            print(common_length(x, 70))
            choice_rm += [False]
        
        choice_rm = edit_lines(choice_rm)

        ind = 0
        for x in overview_removed:
            action = choice_rm[ind]

            if action:
                os.remove(sync_dir + x)
                overview_removed_msg += [print_message('\033[1;31m', '-', x)]
            
            else: 
                print('\rUser cancelled the deletion of ', end = '')
                fill_blank(43, x)
                lx = l_file_path.index(x)
                local_line = '{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                    l_hash_num[lx], l_file_length[lx], l_last_modified[lx], 
                    l_stime[lx], x )
                actual_checksum += [local_line]
            
            ind += 1

        if len(overview_removed) > 0:
            print('')

        print('\n\033[1;32m{0} files uploaded.\033[0m'
              .format(str(len(overview_downloads))))
        for x in overview_downloads: print(x)

        print('\n\033[1;33m{0} files modified.\033[0m'
              .format(str(len(overview_modified))))
        for x in overview_modified: print(x)

        if (os.path.exists(last_local_chksum)):
            os.remove(last_local_chksum)

        checksum = open(last_local_chksum, 'a', encoding = 'utf-8')
        checksum.writelines(actual_checksum)
        checksum.close()

        print('\n\033[1;32m{0}\033[0m'.format('All jobs finished.' ))

    def diff():

        l_hash_num, l_file_length, l_last_modified, l_stime, l_file_path = \
            build_local_checksum()
        ll_hash_num, ll_file_length, ll_last_modified, ll_stime, ll_file_path = \
            read_local_last_checksum()
        r_hash_num, r_file_length, r_last_modified, r_stime, r_file_path = \
            read_remote_checksum()

        for x in range(len(l_file_path)):
            local_file = l_file_path[x]

            if local_file in r_file_path:
                rx = r_file_path.index(local_file)

                # the newer condition
                is_updated = (r_hash_num[rx] != l_hash_num[x]) or \
                             (r_file_length[rx] != l_file_length[x])
                
                is_newer = False
                if local_file in ll_file_path:
                    llx = ll_file_path.index(local_file)
                    is_newer = r_stime[rx] > ll_stime[llx]
                else: is_newer = True

                if is_updated:

                    if not is_newer:
                        print('[r] {:<7} > [l] {:<7} '.format(r_hash_num[rx][:7],
                                                              l_hash_num[x][:7]), end = '')
                        print_message('\033[1;33m', '~', local_file, overwrite = False)
                    
                    else:
                        print('[r] {:<7} > [l] {:<7} '.format(r_hash_num[rx][:7],
                                                              l_hash_num[x][:7]), end = '')
                        print_message('\033[1;33m', '!', local_file, overwrite = False)
                else: pass

            else:

                if l_hash_num[x] in r_hash_num and l_hash_num[x] != manual_zero_md5:

                    remotex = r_hash_num.index(l_hash_num[x])
                    if not r_file_path[remotex] in l_file_path:
                        print('[r] {:<7} > [l] {:<7} '.format(r_hash_num[remotex][:7], 
                                                              '-------'), end = '')
                        print_message('\033[1;33m', 'v', 
                                      r_file_path[remotex], overwrite = False)
                        print('[r] {:<7} > [l] {:<7} '.format('-------', 
                                                              l_hash_num[x][:7]), end = '')
                        print_message('\033[1;30m', '.', local_file, overwrite = False)

                    else:
                        print('[r] {:<7} > [l] {:<7} '.format(r_hash_num[remotex][:7], 
                                                              '-------'), end = '')
                        print_message('\033[1;33m', 'c', r_file_path[remotex], overwrite = False)
                        print('[r] {:<7} > [l] {:<7} '.format('-------', 
                                                              l_hash_num[x][:7]), end = '')
                        print_message('\033[1;30m', '.', local_file, overwrite = False)

                else:        
                    print('[r] {:<7} > [l] {:<7} '.format('-------', l_hash_num[x][:7]), end = '')
                    print_message('\033[1;32m', '+', local_file, overwrite = False)

        for x in range(len(r_file_path)):
            remote_file = r_file_path[x]

            if not remote_file in l_file_path:
                print('[r] {:<7} > [l] {:<7} '.format(r_hash_num[x][:7], '-------'), end = '')
                print_message('\033[1;31m', '-', remote_file, overwrite = False)

    return {
        'fetch': fetch,
        'push': push,
        'diff': diff
    }
