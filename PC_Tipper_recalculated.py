# This code does not qaqc PC_Tipper. Rather, it takes the already
# qaqced PP_Tipper data for all water years and calculates the cumulative sum for
# a particular water year. One could qaqc the existing PC_Tipper data but this is 
# sporadic throughout the database and would require qaqc-ing to fix issues with the
# original PP_Tipper data it was calculated on. It is much more efficient to 
# recalculate this PC_Tipper from the already qaqced PP_Tipper data.

# Written and modified by Julien Bodart (VIU) - 14.07.2024
import pandas as pd 
import numpy as np
import datetime as dtime
from sqlalchemy import create_engine, MetaData, Table
from datetime import datetime

#%% import support functions
import qaqc_functions
from push_sql_function import get_engine, get_metadata, update_records
from qaqc_stations_list import *

#%% establish a connection with MySQL database 'viuhydro_wx_data_v2'
import config
engine = config.main_sql()
metadata = get_metadata(engine)

#%% create list of stations to qaqc for this variable
var = 'PP_Tipper'
var_PC = 'PC_Tipper'
var_PC_flags = var_PC + '_flags'
wx_stations = {name: globals()[name] for name in globals() if name.startswith('clean_')}
wx_stations = [station for station, variables in wx_stations.items() if var in variables]
wx_stations_name = list(map(lambda st: str.replace(st, 'clean_', ''), wx_stations)) # remove 'clean_' for csv export
wx_stations_name_cap = [wx_name.capitalize() for wx_name in wx_stations_name] # capitalise station name

#%% Loop over each station at a time and clean up the PC_Tipper variable
for l in range(len(wx_stations_name)): 
    sql_database = wx_stations_name[l]
    sql_name = wx_stations_name_cap[l]
    print('###### Producing Tipper Cummulative data for station: %s ######' %(sql_name))     
    
    #%% import current data from "qaqc" db (PP_Tipper)
    sql_file = pd.read_sql(sql="SELECT * FROM qaqc_" + sql_database, con = engine)
    sql_file_clean = pd.read_sql(sql="SELECT * FROM clean_" + sql_database, con = engine)

    #%% make sure you only go as far as specific date for all wx stations for current water year
    # Machmell went offline in Feb 2023
    if wx_stations_name[l] == 'machmell':
        sql_file_idx_latest = int(np.flatnonzero(sql_file['DateTime'] == '2023-02-12 11:00:00')[0]) if np.flatnonzero(sql_file['DateTime'] == '2023-02-12 11:00:00').size > 0 else 0   # today's date - 7 days
        sql_file = sql_file[:sql_file_idx_latest+1]
    # for all other stations, qaqc data up to last week
    else:
        qaqc_upToDate = sql_file['DateTime'].iloc[-1] # todays date rounded to nearest hour
        sql_file_idx_latest = int(np.flatnonzero(sql_file['DateTime'] == qaqc_upToDate)[0]) if np.flatnonzero(sql_file['DateTime'] == qaqc_upToDate).size > 0 else 0   # today's date - 7 days  
        # sql_file_idx_latest = int(np.flatnonzero(sql_file['DateTime'] == '2024-02-19 06:00:00')[0]) if np.flatnonzero(sql_file['DateTime'] == '2024-02-19 06:00:00').size > 0 else 0  # arbitrary date
        
    # if sql_file_idx_latest is null, this means the wx station transmission 
    # has stopped between the last time this code ran and the qaqc_upToDate
    # date (i.e. over the last week))
    qaqc_upToDate_clean = (datetime.now()- dtime.timedelta(days=7)).strftime("%Y-%m-%d %H") + ':00:00' # todays date rounded to nearest hour
    sql_file_idx_latest_clean = int(np.flatnonzero(sql_file_clean['DateTime'] == qaqc_upToDate_clean)[0]) if np.flatnonzero(sql_file_clean['DateTime'] == qaqc_upToDate_clean).size > 0 else 0   # today's date - 7 days  

    if sql_file_idx_latest_clean != 0:
        sql_file = sql_file[:sql_file_idx_latest+1]
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
            
        PC_Tipper_final = [] # set up the variable
        
        # start the qaqc process for each water year at specific weather station    
        for k in range(len(yr_range)-1,len(yr_range)):
            print('## For year: %d-%d ##' %(yr_range[k],yr_range[k]+1)) 
    
            # find indices of water years
            start_yr_sql = qaqc_functions.nearest(dt_sql, datetime(yr_range[k], 10, 1))
            end_yr_sql = qaqc_functions.nearest(dt_sql, datetime(yr_range[k]+1, 9, 30, 23, 00, 00))
        
            # select data for the whole water year based on datetime object
            dt_yr = np.concatenate(([np.where(dt_sql == start_yr_sql), np.where(dt_sql == end_yr_sql)]))
            
            # store for plotting
            raw = sql_file[var].iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)]
            PC_tipper = sql_file.copy()
            
            # calculate cumsum 
            data = PC_tipper.loc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1),var].copy()
            PC_tipper_0 = np.cumsum(data) 
            PC_tipper_0 = np.round(PC_tipper_0,2) 
            flags_0 = data.copy()*0 # hack to keep array indices but make all vals 0 for flag
            flags_0[np.isnan(flags_0)] = 0 # make sure there are no nans and if so replace by flag 0
            PC_tipper["PC_Tipper"] = PC_tipper_0
           
            #%% merge flags together into large array, with comma separating multiple
            # flags for each row if these exist
            flags = pd.concat([flags_0],axis=1)
            PC_tipper['PC_Tipper_flags'] = flags.apply(qaqc_functions.merge_row, axis=1)
            
            #%% append to qaqc_arr_final after every k iteration
            PC_Tipper_final.append(PC_tipper.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)])
            
        #%% push qaqced variable to SQL database
        # as above, skip iteration if all PC_Tipper is null
        if sql_file[var].isnull().all() or dt_yr.size == 0:
            continue
        # otherwise, if data (most stations), keep running
        else:
            print('# Writing newly qaqced data to SQL database #') 
            PC_Tipper_final = pd.concat(PC_Tipper_final) # concatenate lists
            sql_qaqc_name = 'qaqc_' + wx_stations_name[l]
            qaqced_array = pd.concat([PC_Tipper_final['DateTime'],PC_Tipper_final[var_PC],PC_Tipper_final[var_PC_flags]],axis=1)
            qaqced_array = qaqced_array.replace(np.nan, None) # replace nans by None for sql database
    
            # import current qaqc sql db and find columns matching the qaqc variable here
            existing_qaqc_sql = pd.read_sql('SELECT * FROM %s' %sql_qaqc_name, engine)
            
            #%%  write data to sql database using brute approach (re-write whole db - quicker on laptop but gets instantly killed on remote desktop)
            # colnames = existing_qaqc_sql.columns
            # col_positions = [i for i, s in enumerate(colnames) if var_PC in s]
            # existing_qaqc_sql[colnames[col_positions]] = pd.concat([qaqced_array[var_PC],qaqced_array[var_PC_flags]],axis=1)
            
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
            # existing_qaqc_sql[var_PC] = existing_qaqc_sql[var_PC].astype('float64')
            # existing_qaqc_sql[var_PC_flags] = existing_qaqc_sql[var_PC_flags].astype('object')
            # existing_qaqc_sql.to_sql(name='%s' %sql_qaqc_name, con=engine, if_exists = 'replace', index=False)
            
            # # make sure you assign 'DateTime' column as the primary column
            # with engine.connect() as con:
            #         con.execute('ALTER TABLE `qaqc_%s`' %wx_stations_name[l] + ' ADD PRIMARY KEY (`DateTime`);')
                            
            #%%  write data to sql database using soft approach (re-write only idx and vars needed - very slow on laptop but fast on remote desktop)
            qaqc_idx_sql = existing_qaqc_sql[var_PC].notna()[::-1].idxmax()+1 # find latest valid value in sql database and fill after that
            dt_qaqc_idx_sql = existing_qaqc_sql['DateTime'].iloc[qaqc_idx_sql] # find matching datetime object in the qaqc db
            qaqc_idx_sql = (np.flatnonzero(qaqced_array['DateTime'] == dt_qaqc_idx_sql)[0]) if np.flatnonzero(qaqced_array['DateTime'] == dt_qaqc_idx_sql).size > 0 else 0
            print('Amount of days to push to qaqc database: %d' %(int((qaqced_array.index[-1] - qaqced_array.index[qaqc_idx_sql])/24)))
            column_mapping = {
                'DateTime': 'DateTime',
                var_PC: var_PC,
                var_PC_flags: var_PC_flags
            }
            update_records(engine, metadata, 'qaqc_' + wx_stations_name[l], qaqced_array[qaqc_idx_sql:], column_mapping)
            
    # skip iteration if the weather station has stopped transmitting for some reasons
    else:
        # if transmission has stopped since last week, skip this station
        print('Careful: %s has stopped transmitting and will not be qaqced until back on live' %(sql_name))     
        continue 
    
# Close the sql connection after the loop has completed
print('## Finished PC_Tipper qaqc for all stations ##')     
engine.dispose()