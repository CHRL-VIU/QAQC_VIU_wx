#%% This code creates an SQL database for each qaqc wx station databases
# all databases are by default filled with nans. The code also assigns the primary
# column in each newly created SQL dabase to DateTime

####### Make sure of the following when you add SQL databases ####### 
# You need to make sure you export the variables with the correct data type. All
# '_flags' should be text or char. All others should be float, except for 
# Datetime and WatYr. If you don't do that, the qaqc_minapp won't work as it
# relies on the same data types across 'clean' and 'qaqc' databases. This can be
# done in python or directly in phpMyAdmin, using the following command:

# for all stations except Stephanies (but include Steph3)    
#ALTER TABLE `qaqc_apelake` CHANGE `Air_Temp` `Air_Temp` FLOAT NULL DEFAULT NULL, 
#CHANGE `BP` `BP` FLOAT NULL DEFAULT NULL, CHANGE `Batt` `Batt` FLOAT NULL 
#DEFAULT NULL, CHANGE `LWL` `LWL` FLOAT NULL DEFAULT NULL, CHANGE `LWU` `LWU` 
#FLOAT NULL DEFAULT NULL, CHANGE `Lysimeter` `Lysimeter` FLOAT NULL DEFAULT 
#NULL, CHANGE `PC_Raw_Pipe` `PC_Raw_Pipe` FLOAT NULL DEFAULT NULL, CHANGE 
#`PC_Tipper` `PC_Tipper` FLOAT NULL DEFAULT NULL, CHANGE `PP_Pipe` `PP_Pipe` 
#FLOAT NULL DEFAULT NULL, CHANGE `PP_Tipper` `PP_Tipper` FLOAT NULL DEFAULT NULL, 
#CHANGE `Pk_Wind_Dir` `Pk_Wind_Dir` FLOAT NULL DEFAULT NULL, CHANGE `Pk_Wind_Speed`
# `Pk_Wind_Speed` FLOAT NULL DEFAULT NULL, CHANGE `RH` `RH` FLOAT NULL DEFAULT 
#NULL, CHANGE `SWE` `SWE` FLOAT NULL DEFAULT NULL, CHANGE `SWL` `SWL` FLOAT NULL 
#DEFAULT NULL, CHANGE `SWU` `SWU` FLOAT NULL DEFAULT NULL, CHANGE `Snow_Depth` 
#`Snow_Depth` FLOAT NULL DEFAULT NULL, CHANGE `Soil_Moisture` `Soil_Moisture` 
#FLOAT NULL DEFAULT NULL, CHANGE `Soil_Temperature` `Soil_Temperature` FLOAT 
#NULL DEFAULT NULL, CHANGE `Solar_Rad` `Solar_Rad` FLOAT NULL DEFAULT NULL, 
#CHANGE `Wind_Dir` `Wind_Dir` FLOAT NULL DEFAULT NULL, CHANGE `Wind_Speed` 
#`Wind_Speed` FLOAT NULL DEFAULT NULL;

# for all stephanies (except Steph3)
# ALTER TABLE `qaqc_steph1` CHANGE `Air_Temp` `Air_Temp` FLOAT NULL DEFAULT NULL, 
# CHANGE `BP` `BP` FLOAT NULL DEFAULT NULL, CHANGE `Batt` `Batt` FLOAT NULL 
# DEFAULT NULL, CHANGE `PC_Raw_Pipe` `PC_Raw_Pipe` FLOAT NULL DEFAULT NULL, CHANGE 
# `PC_Tipper` `PC_Tipper` FLOAT NULL DEFAULT NULL, CHANGE `PP_Tipper` `PP_Tipper` FLOAT NULL DEFAULT NULL, 
# CHANGE `Pk_Wind_Dir` `Pk_Wind_Dir` FLOAT NULL DEFAULT NULL, CHANGE `Pk_Wind_Speed`
#  `Pk_Wind_Speed` FLOAT NULL DEFAULT NULL, CHANGE `RH` `RH` FLOAT NULL DEFAULT 
# NULL, CHANGE `SWE` `SWE` FLOAT NULL DEFAULT NULL, CHANGE `Snow_Depth` 
# `Snow_Depth` FLOAT NULL DEFAULT NULL, CHANGE `Solar_Rad` `Solar_Rad` FLOAT NULL DEFAULT NULL, 
# CHANGE `Wind_Dir` `Wind_Dir` FLOAT NULL DEFAULT NULL, CHANGE `Wind_Speed` 
# `Wind_Speed` FLOAT NULL DEFAULT NULL;

# Written and updated by Julien Bodart (VIU) - 13.07.2024

import pandas as pd 
from sqlalchemy import create_engine
import numpy as np
from datetime import datetime
import datetime as dtime
import os

#%% import support functions
from qaqc_stations_list import *

#%% establish a connection with MySQL database 'viuhydro_wx_data_v2'
import config
engine = config.main_sql()

#%% create list of stations to qaqc for this variable
wx_stations = {name: globals()[name] for name in globals() if name.startswith('clean_')}
wx_stations_name = list(map(lambda st: str.replace(st, 'clean_', ''), wx_stations)) # remove 'clean_' for csv export
wx_stations_name_cap = [wx_name.capitalize() for wx_name in wx_stations_name] # capitalise station name

#%% Loop over each station at a time and clean up the snow depth variable
for l in range(len(wx_stations_name)):
    sql_database = wx_stations_name[l]
    sql_name = wx_stations_name_cap[l]
    print('###### Adding empty rows for last week on sql database for station: %s ######' %(sql_name))     
    
    #%% import current data from "clean" and "qaqc" databases and make sure clean
    # records have no gaps in the DateTime column (i.e. hourly records are 
    # continuous every hour)
    sql_file = pd.read_sql(sql="SELECT * FROM clean_" + sql_database, con = engine)
    sql_file = sql_file.set_index('DateTime').asfreq('h').reset_index() # make sure records are continuous every hour
    sql_file_qaqc = pd.read_sql(sql="SELECT * FROM qaqc_" + sql_database, con = engine)
    
    # make sure all columns between clean and qaqc dbs match each other
    cols_clean = sql_file.columns.tolist()
    cols_qaqc = [col for col in sql_file_qaqc.columns if 'flags' not in col] # remove flags cols
    missing_columns = [col for col in cols_clean if col not in cols_qaqc]
    sql_file = sql_file.drop(columns=missing_columns)

    #%% Only select earliest possible date for full year
    dt_sql = pd.to_datetime(sql_file['DateTime'])    
    qaqc_upToDate = (datetime.now()- dtime.timedelta(days=7)).strftime("%Y-%m-%d %H") + ':00:00' # todays date rounded to nearest hour
    
    # try unless it throws error (which happens only if the transmission 
    # has stopped between the last time this code ran and the qaqc_upToDate
    # date (i.e. over the last week))
    try:
        new_df = sql_file[:sql_file.loc[sql_file['DateTime'] == qaqc_upToDate].iloc[0].name] # today's date - 7 days
    except IndexError:
        # if transmission has stopped since last week, skip this station
        print('Careful: %s has stopped transmitting and will not be qaqced until back on live' %(sql_name))     
        continue

    # add nans if missing records        
    nanout = [c for c in new_df.columns if c not in ['DateTime', 'WatYr']]
    new_df.loc[:, nanout] = np.nan
    
    # add flags columns
    colname = nanout
    colname_flags = [direction + '_flags' for direction in colname]
    
    # merge both dataframes together
    new_df.loc[:, colname_flags] = np.nan
    
    # sort columns by alphabetical names
    colname_new = new_df.columns[2:]
    temp_df = new_df[colname_new]
    temp_df = temp_df[sorted(temp_df.columns)]
    
    # merge into final dataframe
    df_full = pd.concat([new_df['DateTime'], new_df['WatYr'],temp_df],axis=1)
    
    # merge df_full with existing qaqc up to the last qaqc date
    # and replace nans with None
    df_full = df_full.replace({np.nan: None})
    df_full[:sql_file_qaqc.index[-1]+1] = sql_file_qaqc
    #df_full[:sql_file_qaqc.index[-1]+1] = df_full[:sql_file_qaqc.index[-1]+1].replace(np.nan, None) # replace nans by None for sql database
    
    # recalculate water year for specific weather stations in qaqc
    # (new year starts on 10.01.YYYY). If months are 
    # before October, do nothing. Else add +1
    nan_idxs = df_full.loc[pd.isna(df_full['WatYr']), :].index
    if nan_idxs.size:
        WatYrs = []
        for i in range(len(nan_idxs)):
            if int(str(df_full['DateTime'].iloc[nan_idxs[i]]).split('-')[1]) < 10:
                WatYr = int(str(df_full['DateTime'].iloc[nan_idxs[i]]).split('-')[0])
            else:
                WatYr = int(str(df_full['DateTime'].iloc[nan_idxs[i]]).split('-')[0])+1
            WatYrs.append(WatYr) 
            
        df_full.loc[nan_idxs, 'WatYr'] = WatYrs
    
    #%% import database to SQL
    # to import an entirely new database with all historic data
    #df_full.to_sql(name='qaqc_%s' %wx_stations_name[l], con=engine, if_exists = 'append', index=False)
    
    # to import only last week of data
    df_full[sql_file_qaqc.index[-1]+1:].to_sql(name='qaqc_%s' %wx_stations_name[l], con=engine, if_exists = 'append', index=False)

#%% Close the sql connection after the loop has completed
print('## Finished creating empty rows for newly qaqc data for all stations ##')     
try:
    engine.dispose()
except Exception as e:
    print(f"// Error closing (disposing) the connection with SQL - that's ok as long as empty rows are being added weekly in the qaqc_dbs. Error': {e}")
