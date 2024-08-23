# This script analyses all files matching desired extension in folder
# and moves them across to new directory. This is to facilitate processing
# of radar data 
from pathlib import Path

# Move SEGYs
# ----------------------------------
var_name = 'Pk_Wind_Dir'
Path("/v2/merged_figures/" + (var_name)).mkdir(parents=True, exist_ok=True)

import os, shutil
for root, dirs, files in os.walk('/v2/individual_figures/'):
    if var_name not in root:
        continue
    #elif 'Pk' in root: # remove 'Pk' pngs (e.g. Wind variables)
    #    continue
    else:
        for file in files:
            if file.endswith(".png"):
                print(os.path.join(root, file))
    
                # move to new directory
                shutil.copy(os.path.abspath(root + '/' + file), '/v2/merged_figures/' + var_name)
# ---------------------------------
