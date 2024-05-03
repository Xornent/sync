
# ./shared/oss_aliyun.py
#   the aliyun-oss <see oss.console.aliyun.com> implementation of the oss 
#   procedures interface. this file as a plugin will be programmatically loaded
#   by oss.py. see interface definition in oss.py remarks.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import os
import subprocess

required_args = [
    'oss',     # the oss commandline executable
    'bucket',  # the remote bucket name
    'credential', # the oss credential
    'id',         # the oss login id
    'endpoint',   # the remote endpoint
]

# download from server into the local (absolute) corresponding path.
# requires kwargs 'bucket' and 'oss'.
def download_file(remote: str, local: str, kwargs: dict) -> str:
    if os.path.exists(local):
        os.remove(local)

    params = [kwargs['oss'],
        'cp', 'oss://{0}{1}'.format(kwargs['bucket'], remote),
        local.replace('\\', '/'),
        '-c', kwargs['config-file']]
    subprocess.run(params, capture_output = True)
    return '{0}'.format(remote)

# upload to server using absolute file to the remote destfile.
def upload_file(file: str, destfile: str, kwargs: dict) -> int:
    subprocess.run([kwargs['oss'], 'rm', 
                    'oss://{0}{1}'.format(kwargs['bucket'], 
                                          destfile.replace('\\', '/')),
                    '-c', kwargs['config-file']], capture_output = True)
    
    return subprocess.run([kwargs['oss'],
        'cp', file.replace('\\', '/'),
        'oss://{0}{1}'.format(kwargs['bucket'], destfile.replace('\\', '/')),
        '-c', kwargs['config-file']], capture_output =True)

# this is not actually move, since i do not want to actually delete the file
# in the original location. i think this is safer, this makes the move method
# completely identical to copy. but you can implement the move_file in another way.
def move_file(src: str, dest: str, kwargs: dict) -> int:
    subprocess.run([kwargs['oss'], 'rm', 
                    'oss://{0}{1}'.format(kwargs['bucket'], dest.replace('\\', '/')),
                    '-c', kwargs['config-file']], capture_output = True)
    
    return subprocess.run([kwargs['oss'],
        'cp', 'oss://{0}{1}'.format(kwargs['bucket'], src.replace('\\', '/')),
        'oss://{0}{1}'.format(kwargs['bucket'], dest.replace('\\', '/')),
        '-c', kwargs['config-file']], capture_output =True)

def copy_file(src: str, dest: str, kwargs: dict) -> int:
    subprocess.run([kwargs['oss'], 'rm', 
                    'oss://{0}{1}'.format(kwargs['bucket'], dest.replace('\\', '/')),
                    '-c', kwargs['config-file']], capture_output = True)
    
    return subprocess.run([kwargs['oss'],
        'cp', 'oss://{0}{1}'.format(kwargs['bucket'], src.replace('\\', '/')),
        'oss://{0}{1}'.format(kwargs['bucket'], dest.replace('\\', '/')),
        '-c', kwargs['config-file']], capture_output =True)

def init(kwargs: dict):

    with open(kwargs['config-file'], 'w') as cfgfile:
        cfgfile.writelines([
            '[Credentials]',
            '\n    language=en',
            '\n    accessKeySecret=' + kwargs['credential'],
            '\n    accessKeyID=' + kwargs['id'],
            '\n    endpoint=' + kwargs['endpoint']
        ])