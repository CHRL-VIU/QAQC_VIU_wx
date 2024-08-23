# This code attempts to QA/QC the snow depth data in a full year for all wx
# stations and all years

# Written and modified by Julien Bodart (VIU) - 14.07.2024
import pandas as pd 
from datetime import datetime, timedelta
import numpy as np
import datetime as dtime
from sqlalchemy import create_engine, MetaData, Table

# csv file path on server
csv_file_path_server = '/python-scripts/QAQC_VIU_wx/'

#%% import support functions
import qaqc_functions
from push_sql_function import get_engine, get_metadata, update_records
from qaqc_stations_list import *

#%% establish a connection with MySQL database 'viuhydro_wx_data_v2'
import config
engine = config.main_sql()
metadata = get_metadata(engine)

#%% create list of stations to qaqc for this variable
var = 'Snow_Depth'
var_flags = var + '_flags'
wx_stations = {name: globals()[name] for name in globals() if name.startswith('clean_')}
wx_stations = [station for station, variables in wx_stations.items() if var in variables]
wx_stations_name = list(map(lambda st: str.replace(st, 'clean_', ''), wx_stations)) # remove 'clean_' for csv export
wx_stations_name_cap = [wx_name.capitalize() for wx_name in wx_stations_name] # capitalise station name

#%% Loop over each station at a time and clean up the snow_depth variable
for l in range(len(wx_stations_name)): 
    sql_database = wx_stations_name[l]
    sql_name = wx_stations_name_cap[l]
    print('###### Cleaning snow data for station: %s ######' %(sql_name))     
    
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
        elif wx_stations_name[l] == 'placeglacier' and dt_sql[0].year == datetime.now().year: 
            yr_range = np.arange(2023, datetime.now().year) # specify this for placeglacier's first year
        else: 
            yr_range = np.arange(dt_sql[0].year, datetime.now().year) # find min and max years
            
        # remove specific years for specific stations where data is unqaqcable
        if wx_stations_name[l] == 'mountcayley':
            yr_range = np.delete(yr_range, np.flatnonzero(yr_range == 2022))
            
        # remove 2024 year for East Buxton as it's un-qaqcable
        if wx_stations_name[l] == 'eastbuxton':
            yr_range = np.delete(yr_range, np.flatnonzero(yr_range == 2023))
    
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
    
            #%% only qaqc data in the summer period for all previous water years but
            # not for current water year if it has not yet reached summer months 
            
            # First, read in the CSV containing specific summer dates for certain 
            # wx stations. This CSV was created for where the qaqc algorithm fails
            # to detect accurately the start of the summer (or where snow depth
            # reaches approximately 0)
            with open(csv_file_path_server + 'sdepth_zeroing_dates.csv', 'r') as readFile:
                df_csv = pd.read_csv(readFile,low_memory=False)
                csv_dt = pd.to_datetime(df_csv['zero_date'])
                df_csv['zero_date'] = csv_dt.dt.year.values
            name = pd.concat([pd.DataFrame([wx_stations_name[l]],columns=['filename']), pd.DataFrame([yr_range[k]+1],columns=['zero_dates'])], axis=1, join='inner')
    
            # First check if there is a summer value in the database or not yet 
            # (summer value == July 01) i.e. if summer has started yet for this 
            # water year
            if np.where(dt_sql == np.datetime64(datetime(yr_range[k]+1, 7, 1, 00, 00, 00)))[0].size != 0:
                summer = True 
                
            # else if there is a specific date assigned in the CSV to cut off,
            # then it should also be True as summer has started and there is a 
            # a date in the CSV file because the qaqc auto algorithm fails
            elif np.any((df_csv.values == name.values).all(axis=1)) == True:
                summer = True 
            
            # else if no date is assigned in CSV or the summer has not yet arrived,
            # return false so it does not do the qaqc step 6 (zero out summer values)
            else:
                summer = False
                
            # if summer is true from above, then provide indices for start and
            # end of summer
            if summer == True:
                dt_summer_yr = np.concatenate(([np.where(dt_sql == qaqc_functions.nearest(dt_sql, np.datetime64(datetime(yr_range[k]+1, 7, 1, 00, 00, 00)))), np.where(dt_sql == qaqc_functions.nearest(dt_sql, np.datetime64(datetime(yr_range[k]+1, 9, 23, 00, 00, 00))))]))
    
            # store for plotting (if needed)
            raw = sql_file[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            qaqc_arr = sql_file.copy() # array to QAQC
            
            #%% add temporary fix to specific weather stations to correct for any
            # small offsets throughout the time series (usually these are only for
            # current water years. Previous water years will already have been fixed
            # in the databases before running the code)       
            if wx_stations_name[l] == 'mountcayley' and yr_range[k]+1 >= 2024:
                idx_last = int(np.flatnonzero(qaqc_arr['DateTime'] == '2023-10-31 15:00:00')[0])
                if idx_last in qaqc_arr.index:
                    qaqc_arr.loc[dt_yr[0].item():int(np.flatnonzero(qaqc_arr.index == idx_last)[0]),var] = qaqc_arr.loc[dt_yr[0].item():int(np.flatnonzero(qaqc_arr.index == idx_last)[0]),var] - 626.4
                    qaqc_arr.loc[int(np.flatnonzero(qaqc_arr.index == idx_last)[0]):dt_yr[1].item(),var] = qaqc_arr.loc[int(np.flatnonzero(qaqc_arr.index == idx_last)[0]):dt_yr[1].item(),var] +9 # add 9 as offset eyeballed
            
            if wx_stations_name[l] == 'apelake' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]-10.65 # add 10.65 as offset eyeballed
    
            if wx_stations_name[l] == 'claytonfalls' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]-3  # add -3 as offset eyeballed
     
            if wx_stations_name[l] == 'eastbuxton' and yr_range[k]+1 >= 2018:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+10 # add 10 as offset eyeballed
    
            if wx_stations_name[l] == 'klinaklini' and yr_range[k]+1 < 2021:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+25 # add 25 as offset eyeballed
    
            if wx_stations_name[l] == 'klinaklini' and yr_range[k]+1 >= 2022:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]-8 # add -8 as offset eyeballed
            
            if wx_stations_name[l] == 'lowercain' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]-6 # add -6 as offset eyeballed
            
            if wx_stations_name[l] == 'mountarrowsmith' and yr_range[k]+1 < 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+2 # add 2 as offset eyeballed
    
            elif wx_stations_name[l] == 'mountarrowsmith' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+7 # add 7 as offset eyeballed
            
            if wx_stations_name[l] == 'perseverance' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+7 # add 7 as offset eyeballed
                            
            if wx_stations_name[l] == 'uppercruickshank' and yr_range[k]+1 >= 2024:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]-14 # add -14 as offset eyeballed
    
            if wx_stations_name[l] == 'steph3' and yr_range[k]+1 >= 2022:
                qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var] = qaqc_arr.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var]+7 # add 7 as offset eyeballed
    
            if wx_stations_name[l] == 'steph3' and yr_range[k]+1 == 2020:
                idx_nans = np.where(qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)] > 200)[0] + dt_yr[0].item()
                qaqc_arr[var].loc[idx_nans] = np.nan # remove weird values for specific time period in 2019-20
                
            if wx_stations_name[l] == 'steph6' and yr_range[k]+1 == 2019:
                idx_nans_str = int(np.flatnonzero(qaqc_arr['DateTime'] == '2018-10-08 18:00:00')[0])
                idx_nans_end = int(np.flatnonzero(qaqc_arr['DateTime'] == '2018-10-16 15:00:00')[0])
                qaqc_arr.loc[idx_nans_str:idx_nans_end,var] = np.nan # remove weird values for specific time period in 2019-20
              
            if wx_stations_name[l] == 'mountmaya' and yr_range[k]+1 == 2024:
                idx_nans_str = int(np.flatnonzero(qaqc_arr['DateTime'] == '2024-05-01 22:00:00')[0])
                idx_nans_end = int(np.flatnonzero(qaqc_arr['DateTime'] == '2024-05-04 14:00:00')[0])
                qaqc_arr.loc[idx_nans_str:idx_nans_end,var] = np.nan # remove weird values for specific time period in 2019-20
            
            #%% qaqc all data except if it is placeglacier, as the snow_depth is still
            # not yet calibrated (for water year 2024)    
            # for place glacier, assign nans to all summer values and flag 6             
            if wx_stations_name[l] == 'placeglacier' and yr_range[k] == 2023:
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flags = pd.Series(np.full((len(qaqc_arr[var])),6)) # assign flag 6
                data[:] = np.nan # fill with nans
                qaqc_arr[var] = data
                qaqc_arr[var_flags] = flags
                qaqc_arr_final.append(qaqc_arr.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)])
                
            # else for all other weather stations that are not place glacier
            else:
                #%% Apply static range test (remove values where difference is > than value)
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 1
                step_size = 25 # in cm
                qaqc_1, flags_1 = qaqc_functions.static_range_test(qaqc_arr[var], data, flag, step_size)
                qaqc_arr[var] = qaqc_1
                
                #%% Remove all negative values (non-sensical)
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 2
                qaqc_2, flags_2 = qaqc_functions.negtozero(qaqc_arr[var], data, flag)
                qaqc_arr[var] = qaqc_2
            
                #%% Remove duplicate consecutive values
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 3
                qaqc_3, flags_3 = qaqc_functions.duplicates(qaqc_arr[var], data, flag)
                qaqc_arr[var] = qaqc_3
        
                #%% Remove outliers based on mean and std using a rolling window for each
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 4
                st_dev = 4 # specify how many times you want to multiple st_dev (good starting point is 3; 1 is too harsh) 
                qaqc_4, flags_4 = qaqc_functions.mean_rolling_month_window(qaqc_arr[var], flag, dt_sql, st_dev)
                qaqc_arr[var] = qaqc_4
                       
                #%% Remove non-sensical non-zero values in summer for Snow Depth
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 6
               
                # for all water years except current one
                # if yr_range[k] == 2023 and wx_stations_name[l] == 'mountmaya' or summer == False: # Maya came offline before summer started
                if summer == False: 
                    flags_6 = pd.Series(np.zeros((len(qaqc_arr))))        
                elif summer == True:  
                    summer_threshold = 12
                    qaqc_6, flags_6 = qaqc_functions.sdepth_summer_zeroing(qaqc_arr[var], data, flag, dt_yr, dt_summer_yr, summer_threshold, qaqc_arr['DateTime'], wx_stations_name[l], yr_range[k]+1)
                    qaqc_arr[var] = qaqc_6
                    
                #%% one more pass to correct remaining outliers using the step size
                # and different levels until it's all 'shaved off'
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 7
                step_sizes = [20,15,10,5] # in cm
                qaqc_7, flags_7 = qaqc_functions.static_range_multiple(qaqc_arr[var], data, flag, step_sizes)
                qaqc_arr[var] = qaqc_7
                
                #%% Interpolate nans with method='linear' using pandas.DataFrame.interpolate
                # First, identify gaps larger than 3 hours (which should not be interpolated)
                data = qaqc_arr[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
                flag = 8
                max_hours = 3
                qaqc_8, flags_8 = qaqc_functions.interpolate_qaqc(qaqc_arr[var], data, flag, max_hours)
                qaqc_arr[var] = qaqc_8
    
                #%% merge flags together into large array, with comma separating multiple
                # flags for each row if these exist
                flags = pd.concat([flags_1,flags_2,flags_3,flags_4,flags_6,flags_7,flags_8],axis=1)
                qaqc_arr['Snow_Depth_flags'] = flags.apply(qaqc_functions.merge_row, axis=1)
                
                # for simplicity, if flag contains flag 6 amongst other flags in one row,
                # then only keep 6 as all other flags don't matter if it's already been
                # zeroed out (i.e. flag 6 is the dominant flag)
                idx_flags6 = [i for i, s in enumerate(qaqc_arr['Snow_Depth_flags']) if '6' in s]
                qaqc_arr.loc[idx_flags6, 'Snow_Depth_flags'] = '6'
        
                #%% exceptions below for specific manual fixes to the data
                if wx_stations_name[l] == 'cainridgerun' and yr_range[k] == 2019:
                    idx_err = int(np.flatnonzero(qaqc_arr['DateTime'] == '2020-02-21 03:00:00')[0])
                    qaqc_arr.loc[idx_err:dt_yr[1].item()+1, var_flags] = np.nan
                    qaqc_7.iloc[idx_err:dt_yr[1].item()+1] = np.nan
                    qaqc_8.iloc[idx_err:dt_yr[1].item()+1] = np.nan
                    qaqc_arr.loc[idx_err:dt_yr[1].item()+1, var_flags] = 1
                
                #%% append to qaqc_arr_final after every k iteration
                qaqc_arr_final.append(qaqc_arr.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)])
    
        #%% push qaqced variable to SQL database
        # as above, skip iteration if all snow_depth is null
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
print('## Finished SnowDepth qaqc for all stations ##')     
engine.dispose()            