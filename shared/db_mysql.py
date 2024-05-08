
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
    'mysql-pwd',  # the password
    'mysql-user'  # the database user
]

# dump the local database
def dump_database(dump: str, kwargs: dict):
    
    if os.path.exists(dump):
        os.remove(dump)

    with open(dump, 'wb') as file:
        # mysqldump -u_ -p_ --databases _ > _.sql
        outs = subprocess.run([kwargs['mysqldump'], 
                               '-u{0}'.format(kwargs['mysql-user']),
                               '-p{0}'.format(kwargs['mysql-pwd']),
                               '--databases', kwargs['dbname'],

                               '--compact'

                               # the --compact is used to reduce the comments in
                               # the .sql file. more importantly, if you do not
                               # use this trigger, you will find the mysqldump
                               # automatically log the dump time as a comment onto
                               # the tail of the file. and make every dump not
                               # identical ... you will have different md5 and
                               # upload the same database over and over again ...
                               
                               ], stdout = file)

# drop and update database.
def import_database(dump: str, kwargs: dict):

    # mysqladmin -u_ -p_ --databases _ > _.sql
    subprocess.run([kwargs['mysqladmin'], 
                    '-u{0}'.format(kwargs['mysql-user']),
                    '-p{0}'.format(kwargs['mysql-pwd']),
                    'drop', kwargs['dbname']])
    
    subprocess.run([kwargs['mysqladmin'], 
                    '-u{0}'.format(kwargs['mysql-user']),
                    '-p{0}'.format(kwargs['mysql-pwd']),
                    'create', kwargs['dbname']])
    
    with open(dump, 'rb') as fp: 
        outs = subprocess.run([kwargs['mysql'], 
                               '-u{0}'.format(kwargs['mysql-user']),
                               '-p{0}'.format(kwargs['mysql-pwd']),
                               kwargs['dbname']], stdin = fp)

def init(kwargs: dict):
    pass