
# ./shared/local.py:
#   local file manipulations.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

import os
import shutil

# move local. 
def copy_local(file, dest):

    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    
    if os.name == 'nt':
        shutil.copy(file.replace('/', '\\'), dest.replace('/','\\'))
    else: shutil.copy(file, dest)

# copy local.
def move_local(file, dest):

    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    
    if os.name == 'nt':
        shutil.move(file.replace('/', '\\'), dest.replace('/', '\\'))
    else: shutil.move(file, dest)