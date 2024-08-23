# This code attempts to QA/QC the barometric pressure data in a full year for all 
# wx stations and all years

# Written and modified by Julien Bodart (VIU) - 14.07.2024
import pandas as pd 
from datetime import datetime, timedelta
import numpy as np
import datetime as dtime
from sqlalchemy import create_engine, MetaData, Table
import os
#%% import support functions
import qaqc_functions
from push_sql_function import get_engine, get_metadata, update_records
from qaqc_stations_list import *

#%% establish a connection with MySQL database 'viuhydro_wx_data_v2'
os.chdir('/python-scripts')
import config
engine = config.main_sql()
metadata = get_metadata(engine)

#%% create list of stations to qaqc for this variable
var = 'BP'
var_flags = var + '_flags'
wx_stations = {name: globals()[name] for name in globals() if name.startswith('clean_')}
wx_stations = [station for station, variables in wx_stations.items() if var in variables]
wx_stations_name = list(map(lambda st: str.replace(st, 'clean_', ''), wx_stations)) # remove 'clean_' for csv export
wx_stations_name_cap = [wx_name.capitalize() for wx_name in wx_stations_name] # capitalise station name

#%% Loop over each station at a time and clean up the BP variable
for l in range(len(wx_stations_name)):    
    sql_database = wx_stations_name[l]
    sql_name = wx_stations_name_cap[l]
    print('###### Cleaning BP data for station: %s ######' %(sql_name))     
    
    #%% import current data from "clean"
    sql_file = pd.read_sql(sql="SELECT * FROM clean_" + sql_database, con = engine)
        
    #%% time in rennell and datlamen is not rounded to nearest hour
    # round time in the clean db data so it matches the qaqc db
    if wx_stations_name[l] == 'rennellpass' or wx_stations_name[l] == 'datlamen':
        sql_file = sql_file.copy()
        sql_file ['DateTime'] = pd.to_datetime(sql_file['DateTime'])
        sql_file['DateTime'] = sql_file['DateTime'].dt.floor('h')
        deltas = sql_file['DateTime'].diff()[1:]
        same_vals = deltas[deltas < timedelta(hours=1)]
        sql_file = sql_file.drop(same_vals.index)
        sql_file = sql_file.set_index('DateTime').asfreq('h').reset_index() # make sure records are continuous every hour

    # else if not rennell or datlamen (i.e. for all other stations), make sure
    # time is consecutively increasing by one hour, if not add records and place nans
    else:
        sql_file = sql_file.set_index('DateTime').asfreq('h').reset_index() # make sure records are continuous every hour
    
    #%% make sure you only go as far as specific date for all wx stations for current water year
    qaqc_upToDate = (datetime.now()- dtime.timedelta(days=7)).strftime("%Y-%m-%d %H") + ':00:00' # todays date rounded to nearest hour
    sql_file_idx_latest = int(np.flatnonzero(sql_file['DateTime'] == qaqc_upToDate)[0]) if np.flatnonzero(sql_file['DateTime'] == qaqc_upToDate).size > 0 else 0   # today's date - 7 days  
    # sql_file_idx_latest = int(np.flatnonzero(sql_file['DateTime'] == '2024-02-19 06:00:00')[0]) if np.flatnonzero(sql_file['DateTime'] == '2024-02-19 06:00:00').size > 0 else 0  # arbitrary date
    
    # if sql_file_idx_latest is null, this means the wx station transmission 
    # has stopped between the last time this code ran and the qaqc_upToDate
    # date (i.e. over the last week))
    if sql_file_idx_latest != 0:
        sql_file = sql_file[:sql_file_idx_latest]
        # sql_file = sql_file[sql_file_idx_latest:]
        
        #%% Make sure there is no gap in datetime (all dates are consecutive) and place
        # nans in all other values if any gaps are identified
        df_dt = pd.Series.to_frame(sql_file['DateTime'])    
        sql_file = sql_file.set_index('DateTime').asfreq('h').reset_index()
        dt_sql = pd.to_datetime(sql_file['DateTime'])
       
        # get your indices for each water year
        if 10 <= datetime.now().month and datetime.now().month <= 12:
            yr_range = np.arange(dt_sql[0].year, datetime.now().year+1) # find min and max years
        elif wx_stations_name[l] == 'machmell': 
            yr_range = np.arange(dt_sql[0].year, datetime.now().year-1) # find min and max years
        elif wx_stations_name[l] == 'placeglacier' and dt_sql[0].year == datetime.now().year: 
            yr_range = np.arange(2023, datetime.now().year) # specify this for placeglacier's first year
        else: 
            yr_range = np.arange(dt_sql[0].year, datetime.now().year) # find min and max years
            
        qaqc_arr_final = [] # set up the variable
    
        # start the qaqc process for each water year at specific weather station
        # only run for last water year to save memory on server
        for k in range(len(yr_range)-1,len(yr_range)):
            print('## Cleaning data for year: %d-%d ##' %(yr_range[k],yr_range[k]+1)) 
        
            # find indices of water years
            start_yr_sql = qaqc_functions.nearest(dt_sql, datetime(yr_range[k], 10, 1))
            end_yr_sql = qaqc_functions.nearest(dt_sql, datetime(yr_range[k]+1, 9, 30, 23, 00, 00))
        
            # select data for the whole water year based on datetime object
            dt_yr = np.concatenate(([np.where(dt_sql == start_yr_sql), np.where(dt_sql == end_yr_sql)]))
        
            # store for plotting (if needed)
            raw = sql_file[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            qaqc_arr = sql_file.copy() # array to QAQC
            
            #%% Remove values above 120 kpa or below 30 kpa threshold
            # above 120kpa
            data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            flag = 2
            threshold = 120 # in kpa
            qaqc_2, flags_2a = qaqc_functions.reset_max_threshold(qaqc_arr[var], data, flag, threshold)
            qaqc_arr[var] = qaqc_2
            
            # below 25kpa
            data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            flag = 2
            threshold = 25 # in kpa
            qaqc_2, flags_2b = qaqc_functions.reset_min_threshold(qaqc_arr[var], data, flag, threshold)
            qaqc_arr[var] = qaqc_2
            
            # merge flags
            flags2 = pd.concat([flags_2a,flags_2b],axis=1) # merge so you don't lose previous flags 2
            flags_2 = flags2.apply(qaqc_functions.merge_row, axis=1).astype(int) # merge so you don't lose previous flags 2
            
            #%% Apply static range test (remove values where difference is > than value)
            # Maximum value between each step: 4 kpa
            data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            flag = 1
            step_size = 4 # in kpa
            qaqc_1, flags_1 = qaqc_functions.static_range_test(qaqc_arr[var], data, flag, step_size)
            qaqc_arr[var] = qaqc_1
            
            #%% Remove outliers based on mean and std using a rolling window for each
            data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            flag = 4
            st_dev = 4 # specify how many times you want to multiple st_dev (good starting point is 3; 1 is too harsh) 
            qaqc_4, flags_4 = qaqc_functions.mean_rolling_month_window(qaqc_arr[var], flag, dt_sql, st_dev)
            qaqc_arr[var] = qaqc_4
            
            #%% Interpolate nans with method='linear' using pandas.DataFrame.interpolate
            # First, identify gaps larger than 3 hours (which should not be interpolated)
            data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            flag = 8
            max_hours = 3
            qaqc_8, flags_8 = qaqc_functions.interpolate_qaqc(qaqc_arr[var], data, flag, max_hours)
            qaqc_arr[var] = qaqc_8
           
            #%% merge flags together into large array, with comma separating multiple
            # flags for each row if these exist
            flags = pd.concat([flags_1,flags_2,flags_4,flags_8],axis=1)
            qaqc_arr[var_flags] = flags.apply(qaqc_functions.merge_row, axis=1)
            
            #%% append to qaqc_arr_final after every k iteration
            qaqc_arr_final.append(qaqc_arr.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)])
    
        #%% push qaqced variable to SQL database
        # as above, skip iteration if all BP is null
        if sql_file[var].isnull().all() or dt_yr.size == 0:
            continue
        # otherwise, if data (most stations), keep running
        else:        
            print('# Writing newly qaqced data to SQL database #') 
            qaqc_arr_final = pd.concat(qaqc_arr_final) # concatenate lists
            sql_qaqc_name = 'qaqc_' + wx_stations_name[l]
            qaqced_array = pd.concat([qaqc_arr_final['DateTime'],qaqc_arr_final[var],qaqc_arr_final[var_flags]],axis=1)
            qaqced_array = qaqced_array.replace(np.nan, None) # replace nans by None for sql database
    
            # import current qaqc sql db and find columns matching the qaqc variable here
            existing_qaqc_sql = pd.read_sql('SELECT * FROM %s' %sql_qaqc_name, engine)
    
            #%%  write data to sql database using brute approach (re-write whole db - quicker on laptop but gets instantly killed on remote desktop)
            # colnames = existing_qaqc_sql.columns
            # col_positions = [i for i, s in enumerate(colnames) if var in s]
            # existing_qaqc_sql[colnames[col_positions]] = pd.concat([qaqced_array[var],qaqced_array[var_flags]],axis=1)
            
            # # make sure you keep the same variable dtypes when pushing new df to sql
            # metadata_map = MetaData(bind=engine)
            # table_map = Table(sql_qaqc_name, metadata, autoload_with=engine)
            
            # # map SQLAlchemy types to pandas dtypes
            # type_mapping = {
            #     'DATETIME': 'datetime64[ns]',
            #     'DOUBLE': 'float64',
            #     'FLOAT': 'float64',
            #     'TEXT': 'object',
            # }
            
            # # map the correct dytpe in df to sql and push to sql db
            # existing_qaqc_sql = existing_qaqc_sql.astype({col.name: type_mapping.get(str(col.type).upper(), 'object') for col in table_map.columns if col.name in existing_qaqc_sql.columns})      
            # existing_qaqc_sql[var] = existing_qaqc_sql[var].astype('float64')
            # existing_qaqc_sql[var_flags] = existing_qaqc_sql[var_flags].astype('object')
            # existing_qaqc_sql.to_sql(name='%s' %sql_qaqc_name, con=engine, if_exists = 'replace', index=False)
            
            # # make sure you assign 'DateTime' column as the primary column
            # with engine.connect() as con:
            #         con.execute('ALTER TABLE `qaqc_%s`' %wx_stations_name[l] + ' ADD PRIMARY KEY (`DateTime`);')
            
            #%%  write data to sql database using soft approach (re-write only idx and vars needed - very slow on laptop but fast on remote desktop)
            qaqc_idx_sql = existing_qaqc_sql[var_flags].notna()[::-1].idxmax()+1 # find latest valid value in sql database and fill after that
            dt_qaqc_idx_sql = existing_qaqc_sql['DateTime'].iloc[qaqc_idx_sql] # find matching datetime object in the qaqc db
            qaqc_idx_sql = (np.flatnonzero(qaqced_array['DateTime'] == dt_qaqc_idx_sql)[0]) if np.flatnonzero(qaqced_array['DateTime'] == dt_qaqc_idx_sql).size > 0 else 0
            print('Amount of days to push to qaqc database: %d' %(int((qaqced_array.index[-1] - qaqced_array.index[qaqc_idx_sql])/24)))
            column_mapping = {
                'DateTime': 'DateTime',
                var: var,
                var_flags: var_flags
            }
            update_records(engine, metadata, 'qaqc_' + wx_stations_name[l], qaqced_array[qaqc_idx_sql:], column_mapping)
            
    # skip iteration if the weather station has stopped transmitting for some reasons
    else:
        # if transmission has stopped since last week, skip this station
        print('Careful: %s has stopped transmitting and will not be qaqced until back on live' %(sql_name))     
        continue 
    
# Close the sql connection after the loop has completed
print('## Finished BP qaqc for all stations ##')     
engine.dispose()