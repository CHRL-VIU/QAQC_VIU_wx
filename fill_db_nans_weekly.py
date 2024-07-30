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
import re
from datetime import datetime
import datetime as dtime

#%% import support functions
import qaqc_functions

#%% Establish a connection with MySQL database 'viuhydro_wx_data_v2'
engine = create_engine('mysql+mysqlconnector://viuhydro_shiny:.rt_BKD_SB*Q@192.99.62.147:3306/viuhydro_wx_data_v2', echo = False)

#%% extract name of all tables within SQL database and clean up var name list
with engine.connect() as connection:
    result = connection.execute("SHOW TABLES;")
    wx_stations_lst = result.fetchall()
    
wx_stations = []
for i in range(len(wx_stations_lst)):
    lst = re.sub(r'[^\w\s]', '', str(wx_stations_lst[i]))
    wx_stations.append(lst)
   
# remove 'raw' tables, remove all steph (but steph3), and others due to local issues
# or because there is no snowDepth sensor there, and sort out the name formatting
wx_stations = [x for x in wx_stations if "clean" in x ]
wx_stations = [x for x in wx_stations if not "legacy" in x] # remove legacy data for Cairnridgerun
wx_stations = [x for x in wx_stations if not "_test" in x] # remove test databases
wx_stations = [x for x in wx_stations if not "archive" in x] # remove archive from list

# deal with Stephanies that are or are not connected to satellite live transmission
keep_steph = False

# if you don't want Stephanies that are not connected to satellite, then remove
#  all except from Steph 3, 6 and Upper Russell
if keep_steph == False:
    wx_stations = [w.replace('clean_steph3', 'clean_Stephanie3') for w in wx_stations] # rename steph3 so it doesn't get cut out
    wx_stations = [w.replace('clean_steph6', 'clean_Stephanie6') for w in wx_stations] # rename steph6 so it doesn't get cut out
    wx_stations = [w.replace('clean_upperrussell', 'clean_Upper') for w in wx_stations] # rename upper russell so it doesn't get cut out
    wx_stations = [x for x in wx_stations if not "steph" in x] # remove all stephanies
    wx_stations = [w.replace('clean_Upper', 'clean_upperrussell') for w in wx_stations] # rename machmellkliniklini back to original
    wx_stations = [w.replace('clean_Stephanie3', 'clean_steph3') for w in wx_stations] # rename steph3 back to original
    wx_stations = [w.replace('clean_Stephanie6', 'clean_steph6') for w in wx_stations] # rename steph6 back to original
    wx_stations = [w.replace('clean_Upper', 'clean_upperrussell') for w in wx_stations] # rename machmellkliniklini back to original
    stephs = []
    
# else if you want Stephanies not connected to satellite, select specific ones 
else:
    stephs = ['steph1', 'steph2', 'steph4', 'steph7', 'steph8', 'russellmain'] # string with all Stephanies except Steph3, 6 and upper russell

wx_stations_name = list(map(lambda st: str.replace(st, 'clean_', ''), wx_stations)) # remove 'clean_' for csv export
wx_stations_name_cap = [wx_name.capitalize() for wx_name in wx_stations_name] # capitalise station name

#%% Loop over each station  and push only the rows that need qaqcing (last week)
for l in range(len(wx_stations_name)):
    sql_database = wx_stations_name[l]
    sql_name = wx_stations_name_cap[l]
    print('###### Creating dummy sql database for station: %s ######' %(sql_name))     
    
    #%% import current data from "clean" and "qaqc" databases and make sure clean
    # records have no gaps in the DateTime column (i.e. hourly records are 
    # continuous every hour)
    with engine.connect() as connection:
        sql_file = pd.read_sql(sql="SELECT * FROM clean_" + sql_database, con=connection)
        sql_file = sql_file.set_index('DateTime').asfreq('h').reset_index()
        sql_file_qaqc = pd.read_sql(sql="SELECT * FROM qaqc_" + sql_database, con=connection)

    #%% Only select earliest possible date for full year
    dt_sql = pd.to_datetime(sql_file['DateTime'])    
    
    #%% only keep data from oldest to newest default date except for exceptions  
    # Stephs not connected to satellite have data up to Oct 2023
    if wx_stations_name[l] in stephs: 
        end_yr_sql = qaqc_functions.nearest(dt_sql, datetime(2023, 9, 30, 23, 00, 00))
        new_df = sql_file.loc[:np.where(sql_file['DateTime'] == end_yr_sql)[0][0]]
     
    # Machmell went offline in Feb 2023
    elif wx_stations_name[l] == 'machmell':
        end_yr_sql = qaqc_functions.nearest(dt_sql, datetime(2023, 2, 12, 11, 00, 00))
        new_df = sql_file.loc[:np.where(sql_file['DateTime'] == end_yr_sql)[0][0]]
        
    # otherwise if any other stations, then select last week as latest date
    else:
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
    with engine.connect() as connection:
        df_full[sql_file_qaqc.index[-1]+1:].to_sql(name='qaqc_%s' %wx_stations_name[l], con=connection, if_exists = 'append', index=False)

#%% Close the sql connection after the loop has completed
print('## Finished creating empty rows for newly qaqc data for all stations ##')     
engine.dispose()