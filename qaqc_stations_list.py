# This python script contains a list of weather station names and variables
# to qaqc. If a variable is not found in a specific weather station, it is likely
# to be because it does not exist in "clean" database. More rarely, it is because  
# the specific variable is difficult to qaqc automatically due to various issues
# with the sensor. To qaqc additional variables or weather stations, simply add
# the specific variable or weather station to this list and the qaqc process
# will import the data and qaqc it 

# Compiled by Julien Bodart (VIU) - 19.07.2024

#%% To qaqc (22 stations in total, as of 19.07.2024)
clean_apelake = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_cainridgerun = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth']
clean_claytonfalls = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_datlamen = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed']
clean_eastbuxton = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Snow_Depth']
clean_homathko = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_klinaklini = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_lowercain = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Snow_Depth', 'SWE']
clean_machmellkliniklini = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_mountarrowsmith = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_mountcayley = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth']
clean_mountmaya = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
clean_perseverance = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_placeglacier = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth'] # 'Snow_Depth' is not yet calibrated
clean_plummerhut = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir'] # 'Snow_Depth removed due to impossible automated qaqc process there
clean_rennellpass = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed'] # 'Snow_Depth removed due to impossible automated qaqc process there
clean_steph3 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
clean_steph6 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
clean_tetrahedron = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_uppercruickshank = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']
clean_upperrussell = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe']
clean_upperskeena = ['Air_Temp', 'RH', 'BP', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Pk_Wind_Dir', 'Snow_Depth', 'SWE']

#%% not yet in the qaqc pipeline (Stephs are not connected to live transmission
# and Machmell station is down since 2023)
# clean_steph1 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
# clean_steph2 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'PC_Raw_Pipe', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
# clean_steph4 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
# clean_steph7 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
# clean_steph8 = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed', 'Snow_Depth']
# clean_russellmain = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Pk_Wind_Speed']
# clean_machmell = ['Air_Temp', 'RH', 'PP_Tipper', 'PC_Tipper', 'Wind_Speed', 'Wind_Dir', 'Pk_Wind_Speed']

#%%

