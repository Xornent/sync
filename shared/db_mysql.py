
# ./shared/db_mysql.py
#   mysql import and export from files.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import os
import subprocess

required_args = [
    'mysql',      # the mysql commandline executable
    'mysqladmin', # the mysqladmin commandline executable
    'mysqldump',  # the mysqldump commandline executable
    'password',   # the password
    'user'        # the database user
]

# dump the local database
def dump_database(dump: str, kwargs: dict):
    
    if os.path.exists(dump):
        os.remove(dump)

    with open(dump, 'wb') as file:
        # mysqldump -u_ -p_ --databases _ > _.sql
        outs = subprocess.run(['mysqldump', 
                               '-u{0}'.format(kwargs['user']),
                               '-p{0}'.format(kwargs['password']),
                               '--databases', kwargs['dbname']], stdout = file)

# drop and update database.
def import_database(dump: str, kwargs: dict):

    # mysqladmin -u_ -p_ --databases _ > _.sql
    subprocess.run(['mysqladmin', 
                    '-u{0}'.format(kwargs['user']),
                    '-p{0}'.format(kwargs['password']),
                    'drop', kwargs['dbname']])
    
    subprocess.run(['mysqladmin', 
                    '-u{0}'.format(kwargs['user']),
                    '-p{0}'.format(kwargs['password']),
                    'create', kwargs['dbname']])
    
    with open(dump, 'rb') as fp: 
        outs = subprocess.run(['mysql', 
                               '-u{0}'.format(kwargs['user']),
                               '-p{0}'.format(kwargs['password']),
                               kwargs['dbname']], stdin = fp)

def init(kwargs: dict):
    pass