#%% Repository of all functions associated with the qaqc of all wx station
# data, irrespective of wx station or wx variable

#%% Import functions
import pandas as pd 
import numpy as np
from itertools import groupby
import math

# csv file path on server
csv_file_path_server = '/python-scripts/QAQC_VIU_wx/'

#%% Static range test (result: FAIL if TRUE)
def static_range_test(data_all, data_subset, flag, step):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()

    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    # only select non-nan data points
    data = data_subset
    idx_exist = (data[data.isnull()==False].index.tolist()) # indices of existing values
    data = data[idx_exist]
    
    for i in range(1,len(data)):
        # only do the following loop on non-nan data and make sure there isn't more
        # than arbitrary 72 data points between non-nan values to avoid any 
        # large outliers being removed due to lengthier gap in data
        if abs(data.iloc[i] - data.iloc[i-1]) > step and data.index[i]-data.index[i-1] < 72:
            idx = data.index[i]
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag         
    return data_all, flag_arr


#%% shave off outliers (similar to static_range_test function but it repeats 
# the process for multiple steps)
def static_range_multiple(data_all, data_subset, flag, steps):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))

    for h in range(len(steps)):
        step = steps[h]
        data = data_subset
        idx_exist = (data[data.isnull()==False].index.tolist()) # indices of existing values
        data = data[idx_exist]
        
        for i in range(1, len(data)):
            if abs(data[data.index[i]] - data[data.index[i-1]]) > step:
                idx = data.index[i]
                data_subset[idx] = np.nan
                data_all.loc[idx] = np.nan
                flag_arr.loc[idx] = flag         
    return data_all, flag_arr

#%% Remove duplicate values (only if there are 3x duplicate values)
def duplicates(data_all, data_subset, flag):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()

    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    for i in range(len(data_subset)-2):
        if abs(data_subset.iloc[i+1] - data_subset.iloc[i]) == 0 and abs(data_subset.iloc[i+2] - data_subset.iloc[i+1]) == 0:
            idx = data_subset.index[i]
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag        
    return data_all, flag_arr

#%% Remove duplicate values of 0% or 100% over specific window size
def duplicates_window(data_all, data_subset, flag, window, threshold):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    for i in range(len(data_subset)-window):
        # for duplicate values at 100
        if threshold == 100 and all(data_subset.iloc[i:i+window] == threshold):
            idx = data_subset.index[i:i+window]
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag  
            
        # for duplicate values at 0
        elif threshold == 0 and all(data_subset.iloc[i:i+window] == threshold):
            idx = data_subset.index[i:i+window]
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag      
            
    return data_all, flag_arr

#%% Remove duplicate values over specific window size. Developped for Wind Direction
# and appears to work better than the earlier function's version as it does
# not rely on setting a specific threshold and relies instead on np.diff
# to find difference between adjacent values and calculate if those duplicates
# are found over a window greater than the one set in the parameters
def duplicates_window_WindDir(data_all, data_subset, flag, window):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()

    flag_arr = pd.Series(np.zeros((len(data_all))))
    end = False # in case the last elements in the ts are not duplicates
  
    # find first np.diff and add 1 to last index in array if the last index is 
    # a duplicate value (necessary for the below code to correctly identify
    # dupliates towards the end of the timeseries)
    diff = np.diff(data_subset)
    if diff[-1] == 0:
        data_subset.iloc[-1] = 1 # temp arbitrary value
        end = True # change the end variable in case duplicates finish the ts
    
    # find (second) proper np.diff and identify indices of non-duplicates
    diff = np.diff(data_subset)
    idx_jumps = np.flatnonzero(diff!= 0) # only keep indices indicating duplicates
    
    # make sure index 0 is fist index (in case it's not)
    if idx_jumps[0] != 0:
        idx_jumps = np.insert(idx_jumps, 0, 0) 
                
    # place nans for all duplicate values over specific window size. Make sure
    # if duplicates are found at the end of the ts, then you add +2 to the indices
    # to cope with the np.diff function
    for i in range(len(idx_jumps)-1):
        if idx_jumps[i+1]-idx_jumps[i] > window:
            idx = data_subset.index[idx_jumps[i]+1:idx_jumps[i+1]+1]
            
            # in case duplicates are found at the end of the ts
            if end == True and i == len(idx_jumps)-1:
                idx = data_subset.index[idx_jumps[i]+1:idx_jumps[i+1]+2] # +2
            
            # place nans and add a flag number
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag 
            
    return data_all, flag_arr

#%% Breakpoint analysis to detect summer trend and zero out values after that 
# (e.g. Snow Depth). Works kind of well (e.g Upper Skeena), but still remains fidly
# and needs more work to be efficient and not cut off important data before the break
# =============================================================================
# def SnowDepth_summer_zeroing(data_all, data_subset, threshold, dt_yr, dt_summer_yr, flag):
#     flag_arr = pd.Series(np.zeros((len(data_all))))
#     
#     # find index in data of maximum gradient change
#     slope_change_summer = np.gradient(data_subset)
#     
#     # Mask out values before June 1st
#     june_idx = (dt_summer_yr[0] - 24 * 30) - data_subset.index[0]
#     slope_change_summer[:june_idx[0]] = np.nan
#     
#     # Find indices where data_subset is within the threshold
#     near_zero_indices = np.where(np.abs(data_subset.values) <= threshold)[0]
#     
#     # Find the maximum gradient change within the near-zero indices
#     max_gradient_change_idx = -1
#     max_gradient_change = np.nan
#     
#     for idx in near_zero_indices:
#         if idx >= june_idx:
#             if np.isnan(max_gradient_change) or slope_change_summer[idx] < max_gradient_change:
#                 max_gradient_change = slope_change_summer[idx]
#                 max_gradient_change_idx = idx
#     
#     # Ensure that the detected index is part of a sequence near zero
#     sequence_length_threshold = 5  # Minimum length of sequence near zero
#     
#     if max_gradient_change_idx != -1:
#         start_idx = max_gradient_change_idx
#         end_idx = max_gradient_change_idx
#     
#         # Extend the sequence to the left
#         while start_idx > 0 and np.abs(data_subset.values[start_idx - 1]) <= threshold:
#             start_idx -= 1
#     
#         # Extend the sequence to the right
#         while end_idx < len(data_subset) - 1 and np.abs(data_subset.values[end_idx + 1]) <= threshold:
#             end_idx += 1
#     
#         # Check if the sequence length is above the threshold
#         if end_idx - start_idx + 1 >= sequence_length_threshold:
#             idx_summer_sequence = max_gradient_change_idx + data_subset.index[0]
#         else:
#             idx_summer_sequence = None
#     else:
#         idx_summer_sequence = None
#         
#     # store for plotting
#     idxs = np.arange(idx_summer_sequence,dt_yr[1].item()+1)
#     data_all[idxs] = 0
#     flag_arr[idxs] = flag          
# 
#     return data_all, flag_arr
# =============================================================================

#%% Remove non-sensical non-zero values in summer for snow depth variable
# Find all values below threshold, then find the longest consecutive 
# list of these values (e.g. summer months) and replace them by 0
# These values are all likely wrong and correspond to sensor drift,
# vegetation change, site visits, etc. Only caveat to this is that certain
# stations flatten out earlier in the summer, so the oode does not pick these 
# up well. Instead, a csv with dates when snow melt flattens around zero is imported
def sdepth_summer_zeroing(data_all, data_subset, flag, dt_yr, dt_summer_yr, summer_threshold, dt, wx_stations_name, year):

    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    data_summer = data_all.iloc[np.arange(dt_summer_yr[0].item(),dt_summer_yr[1].item()+1)]

    # Read in the CSV containing specific summer dates for certain wx stations
    with open(csv_file_path_server + 'sdepth_zeroing_dates.csv', 'r') as readFile:
        df_csv = pd.read_csv(readFile,low_memory=False)
        csv_dt = pd.to_datetime(df_csv['zero_date'])
        df_csv['zero_date'] = csv_dt.dt.year.values
        
    # calculate a maximum acceptable threshold - either mean value in summer 
    # months or if this is too small, a specific value (suggested to be 
    # 12 cm) based on eyeballing of the data in other wx stations or years
    mean_value_summer = np.mean(data_summer)
    arbitrary_value = summer_threshold
    threshold = mean_value_summer > arbitrary_value # check whichever is >
    
    # if there is specific date in the csv, then run below
    name = pd.concat([pd.DataFrame([wx_stations_name],columns=['filename']), pd.DataFrame([year],columns=['zero_dates'])], axis=1, join='inner')
    if np.any((df_csv.values == name.values).all(axis=1)) == True:
        idx = int(np.flatnonzero((df_csv.values == name.values).all(axis=1)))
        idx_longest_sequence = int(np.flatnonzero((csv_dt[idx] == dt)))

    # else if there is no specific dates in the csv, then run below
    else:
        if threshold == True: # if mean is bigger, then use this as threshold
            data_bool = data_all.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)].copy() < mean_value_summer
            
        else: # else if mean is smaller, then use arbitrary value as threshold
            data_bool = data_all.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)].copy() < arbitrary_value
        data_bool = data_bool.replace({True: 1, False: 0}).infer_objects(copy=False)
        data_bool[data_subset[data_subset.isnull()].index] = 1 # replace nans with 1
        
        # find index of longest sequence, making sure you're not picking up
        # a longer sequence at the start of the timeseries (e.g. in early winter)
        # hence the "data_bool.iloc[0:round(len(data)/2)]"
        # which is used arbitrarily so that it does not pick up indices earlier than
        # Spring onwards
        data_bool.iloc[0:round(len(data_subset)/2)] = 0
        idx_longest_sequence = data_bool.index[max(((lambda y: (y[0][0], len(y)))(list(g)) for k, g in groupby(enumerate(data_bool==1), lambda x: x[1]) if k), key=lambda z: z[1])[0]]
    
    data_all.loc[np.arange(idx_longest_sequence,dt_yr[1].item()+1)] = 0
    flag_arr.loc[np.arange(idx_longest_sequence,dt_yr[1].item()+1)]  = flag          

    return data_all, flag_arr

#%% Breakpoint analysis to detect summer trend and zero out values after that (e.g. SWE)
# works kind of but the other code works better
# =============================================================================
# def SWE_summer_zeroing(data_all, data_subset, dt_yr, dt_summer_yr, flag):
#     flag_arr = pd.Series(np.zeros((len(data_all))))
#     
#     # find index in data of maximum gradient change
#     slope_change_summer = np.gradient(data_subset)
#     
#     # find index of longest sequence, making sure you're not picking up
#     # a longer sequence at the start of the timeseries (e.g. in early winter)
#     # hence the "data_bool.iloc[0:round(len(data_subset)/2)]"
#     # which is used arbitrarily so that it does not pick up indices earlier than
#     # Spring onwards
#     june_idx = (dt_summer_yr[0]-24*30) - data_subset.index[0] # index for 06-01 in slope_change_summer
#     slope_change_summer[np.arange(0,june_idx)] = np.nan # all values before are nan
#     idx_summer_sequence = np.nanargmin(slope_change_summer) + data_subset.index[0]  # index for summer sequence in data array
#     
#     # store for plotting
#     idxs = np.arange(idx_summer_sequence,dt_yr[1].item()+1)
#     data_all[idxs] = 0
#     flag_arr[idxs] = flag          
# 
#     return data_all, flag_arr
# =============================================================================

def SWE_summer_zeroing(data_all, data_subset, flag, dt_yr, dt_summer_yr, summer_threshold, dt, wx_stations_name, year):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    data_summer = data_all.iloc[np.arange(dt_summer_yr[0].item(),dt_summer_yr[1].item()+1)]

    # Read in the CSV containing specific summer dates for certain wx stations
    # this is for stations or years where the breakpoint analysis does not work
    # well. First run the code and assess if it detects the summer transition
    # properly. If you see it doesn't, then enter manually the rough date by 
    # eye-balling it and put it into the csv. If it's there, the code will pull
    # it and set the summer at this date
    with open(csv_file_path_server + 'SWE_zeroing_dates.csv', 'r') as readFile:
        df_csv = pd.read_csv(readFile,low_memory=False)
        csv_dt = pd.to_datetime(df_csv['zero_date'])
        df_csv['zero_date'] = csv_dt.dt.year.values
        
    # calculate a maximum acceptable threshold - either mean value in summer 
    # months or if this is too small, a specific value (suggested to be 
    # 12 cm) based on eyeballing of the data in other wx stations or years
    mean_value_summer = np.mean(data_summer)
    arbitrary_value = summer_threshold
    threshold = mean_value_summer > arbitrary_value # check whichever is >
    
    # if there is specific date in the csv (i.e. where the automated summer 
    # detection does not work properly), then run below
    name = pd.concat([pd.DataFrame([wx_stations_name],columns=['filename']), pd.DataFrame([year],columns=['zero_dates'])], axis=1, join='inner')
    if np.any((df_csv.values == name.values).all(axis=1)) == True:
        idx = int(np.flatnonzero((df_csv.values == name.values).all(axis=1))[0]) if np.any((df_csv.values == name.values).all(axis=1)) else None
        idx_longest_sequence = np.where(csv_dt[idx] == dt)[0][0]

    # else if there is no specific dates in the csv (i.e. where the below code
    # works well), then run the below
    else:
        if threshold == True: # if mean is bigger, then use this as threshold
            data_bool = data_all.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)] < mean_value_summer
            
        else: # else if mean is smaller, then use arbitrary value as threshold
            data_bool = data_all.iloc[np.arange(dt_yr[0].item(),dt_yr[1].item()+1)] < arbitrary_value
        data_bool = data_bool.replace({True: 1, False: 0}).infer_objects(copy=False)
        data_bool[data_subset[data_subset.isnull()].index] = 1 # replace nans with 1
        
        # find index of longest sequence, making sure you're not picking up
        # a longer sequence at the start of the timeseries (e.g. in early winter)
        # hence the "data_bool.iloc[0:round(len(data)/2)]"
        # which is used arbitrarily so that it does not pick up indices earlier than
        # Spring onwards
        data_bool.iloc[0:round(len(data_subset)/2)] = 0
        idx_longest_sequence = data_bool.index[max(((lambda y: (y[0][0], len(y)))(list(g)) for k, g in groupby(enumerate(data_bool==1), lambda x: x[1]) if k), key=lambda z: z[1])[0]]
    
    data_all[np.arange(idx_longest_sequence,dt_yr[1].item()+1)] = 0
    flag_arr[np.arange(idx_longest_sequence,dt_yr[1].item()+1)]  = flag          

    return data_all, flag_arr
    
#%% Remove values above the mean of a sliding window of sample length "window_len" 
def mean_sliding_window(data_all, data_subset, flag, window_len, mean_sliding_val):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    idx_exist = (data_subset.iloc[:].loc[data_subset.isnull()==False].index.tolist()) # indices of existing values
    max_outliers = data_subset[idx_exist] # only keep non-nan values
    
    # first apply window for i to i-window_len
    for i in range(len(max_outliers)-window_len):
        window = max_outliers[i:i+window_len]
        if abs(max_outliers.iloc[i] - window.mean()) > mean_sliding_val:
            idx = max_outliers.index[i]
            data_all.loc[idx] = np.nan # place nans if outliers
            flag_arr.loc[idx] = flag          

    # then apply window for i+window_len to i to get remaining outliers    
    for i in range(window_len,len(max_outliers)):
        window = max_outliers[i-window_len:i]
        if abs(max_outliers.iloc[i] - window.mean()) > mean_sliding_val:
            idx = max_outliers.index[i]
            data_all.loc[idx] = np.nan
            flag_arr.loc[idx] = flag        
    
    return data_all, flag_arr

#%% Remove all negative values
def negtozero(data_all, data_subset, flag):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))

    for i in range(len(data_subset)-1):
        if data_subset.iloc[i] < 0:
            idx = data_subset.index[i]
            data_all.loc[idx] = 0 
            flag_arr.loc[idx] = flag        
    
    return data_all, flag_arr

#%% Remove all values above specific threshold
def reset_max_threshold(data_all, data_subset, flag, threshold):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))

    for i in range(len(data_subset)-1):
        if data_subset.iloc[i] > threshold:
            idx = data_subset.index[i]
            data_all.loc[idx] = np.nan 
            flag_arr[idx] = flag        
    
    return data_all, flag_arr

#%% Remove all values below specific threshold
def reset_min_threshold(data_all, data_subset, flag, threshold):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))

    for i in range(len(data_subset)-1):
        if data_subset.iloc[i] < threshold:
            idx = data_subset.index[i]
            data_all.loc[idx] = np.nan 
            flag_arr.loc[idx] = flag        
    
    return data_all, flag_arr

#%% Reset timeseries to zero at start of water year if it's not already the case
def reset_zero_watyr(data_all, data_subset, flag):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()

    flag_arr = pd.Series(np.zeros((len(data_all))))

    idx_first_valid = data_subset.first_valid_index() # first non-nan value in series
    if data_subset.loc[idx_first_valid] != 0:
       data_all[data_subset.index] = data_subset - data_subset.loc[idx_first_valid]
       flag_arr[data_subset.index] = flag        
       
    return data_all, flag_arr

#%% Remove outliers based on mean and std using a rolling window for each
# month of the year
def mean_rolling_month_window(data_all, flag, dt_sql, sd):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    dt_months = dt_sql.dt.month.values
    deltas = np.diff(dt_months)
    gaps = np.append(-1, np.flatnonzero(deltas == 1)) # spits out any gaps > one month. -1 is for loop below to provide index 0 at start
    
    for i in range(len(gaps)):
        if i < len(gaps)-1: # for all indices except last [i]
            idx = [gaps[i]+1,gaps[i+1]]            
        else: # for last index [i]
            idx = [gaps[i]+1,len(dt_months)-1]
            
        data_mth = data_all.iloc[np.arange(idx[0],idx[1]+1)].copy() # all data from month [i] with index matching bigger array
        outliers = data_mth[data_mth > data_mth.mean() + sd*(data_mth.std())] # all outliers in this month matching index of bigger array

        data_all.loc[outliers.index] = np.nan 
        flag_arr.loc[outliers.index] = flag
      
    return data_all, flag_arr

#%% Interpolate qaqced wx station data over specific length of time (max_hours)
def interpolate_qaqc(data_all, data_subset, flag, max_hours):

    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    mask = data_subset.isna()
    mask = (mask.groupby((mask != mask.shift()).cumsum()).transform(lambda x: len(x) <= max_hours)* mask)

    idx = data_subset[np.logical_or(mask == True, data_subset == np.nan)].index
    interpolated = data_subset.interpolate() #( interpolate all nans
    data_all.loc[idx] = np.round(interpolated[idx], 1)
    flag_arr.loc[idx] = flag        

    return data_all, flag_arr

#%% Interpolate qaqced wx station data for Relative Humidity
# RH cannot be interpolated on its own. It first needs to be converted to EA
# using Air_Temperature at each datapoint. If Air_Temp is nan, RH cannot be 
# converted to EA and thus cannot be interpolated 
def interpolate_RH_qaqc(data_all_rh, data_subset_rh, data_subset_temp, flag, max_hours):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all_rh = data_all_rh.copy()
    data_subset_rh = data_subset_rh.copy()
    data_subset_temp = data_subset_temp.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all_rh))))
    
    # find index of nans in Air_Temp and place nans for corresponding index in RH
    nan_temp = np.where(data_subset_temp.isna()) # find index of nans in Air_Temp
    data_subset_rh.iloc[nan_temp] = np.nan # make nan index nans in RH
    
    # calculate saturated vapour pressure from air temperature
    estar = data_subset_temp.copy()
    for i in range(len(data_subset_temp)):
        if data_subset_temp.iloc[i] <= 0:
            estar[i] = 0.611 * math.exp((21.88 * data_subset_temp.iloc[i]) / (data_subset_temp.iloc[i] + 265.5))
        else:
            estar[i] = 0.611 * math.exp((17.27 * data_subset_temp.iloc[i]) / (data_subset_temp.iloc[i] + 237.3))
    
    # convert RH to vapour pressure using saturated vapour pressure when RH is non-nans
    vp = (estar * data_subset_rh) / 100
    
    # find nans in RH that are less than 3 hours
    mask_vp = vp.isna()
    mask_vp = (mask_vp.groupby((mask_vp != mask_vp.shift()).cumsum()).transform(lambda x: len(x) <= max_hours)* mask_vp)
    idx = vp[np.logical_or(mask_vp == True, vp == np.nan)].index
    
    # interpolate data
    interpolated = vp.interpolate() #( interpolate all nans
    vp_interpolated = np.round(interpolated[idx],1) # place newly interpolated values into the master array and round to nearest one decimal 

    # convert back to RH after interpolation
    vp[idx] = vp_interpolated
    data_subset_rh_interpolated = 100 * (vp / estar)
    
    # avoid -inf in data if division is impossible
    data_subset_rh_interpolated = np.maximum(0,data_subset_rh_interpolated)
    data_subset_rh_interpolated = np.minimum(100,data_subset_rh_interpolated)
    
    data_all_rh[idx] = np.round(data_subset_rh_interpolated[idx],1) # place newly interpolated values into the master array and round to nearest one decimal 
    flag_arr[idx] = flag        

    return data_all_rh, flag_arr

#%% merge individual arrays together and split by ','. Make sure that if there
# are multiple of the same flag onto one element (e.g. when an additional
# pass at the filtering for one qaqc step results in two outliers being removed
# with one flag number given that is the same for both steps (e.g. flag_1 = [1,1]
# then keep only one of the flags))
def merge_row(row):
    if all(element == 0 for element in row):
        return '0'
    else:
        non_zero_elements = [str(int(element)) for element in row if element != 0]
        if len(non_zero_elements) == 2 and non_zero_elements[0] == non_zero_elements[1]:
            return non_zero_elements[0] # where multiple flags exists
        else:
            return ','.join(non_zero_elements) 

#%% function to find nearest date
def nearest(items, pivot):
    return min(items, key=lambda x: abs(x - pivot))

#%% Remove non-sensical zero values. This is ideal for air_temperature where a zero value
# which is not bounded by i-1 and i+1 values which are above a certain threshold
# (e.g. -3 to 3), then you can assume the zero is not a realistic value
def false_zero_removal(data_all, data_subset, flag, threshold):

    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    idx_exist = (data_subset.iloc[:].loc[data_subset.isnull()==False].index.tolist()) # indices of existing values
    data_nonnan = data_subset[idx_exist] # only keep non-nan values

    for i in range(1,len(data_nonnan)-1):
        if data_nonnan.iloc[i] == 0 and abs(data_nonnan.iloc[i-1] - data_nonnan.iloc[i]) >= threshold or data_nonnan.iloc[i] == 0 and abs(data_nonnan.iloc[i+1] - data_nonnan.iloc[i]) >= threshold:
            idx = data_nonnan.index[i]
            data_all.loc[idx] = np.nan # place nans if duplicates found
            flag_arr.loc[idx] = flag        

    return data_all, flag_arr

#%% Fix jumps in precipitation data from sudden drainage events during site visits
def precip_drainage_fix(data_all, data_subset, flag, dt_yr, dt, wx_stations_name, year):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    # Read in the CSV containing specific summer dates for certain wx stations
    with open(csv_file_path_server + 'PrecipPipeRaw_drain.csv', 'r') as readFile:
        df_csv = pd.read_csv(readFile,low_memory=False)
        csv_dt_pre = pd.to_datetime(df_csv['pre_drain'], errors='coerce')
        csv_dt_post = pd.to_datetime(df_csv['post_drain'])
        df_csv['post_drain'] = csv_dt_post.dt.year.values
        pre_drain_dt = csv_dt_pre.values
        post_drain_dt = csv_dt_post.values
        
    # find matching datetimes between csv and the current water year + name of station
    name = pd.concat([pd.DataFrame([wx_stations_name],columns=['filename']), pd.DataFrame([year],columns=['watyr'])], axis=1, join='inner')
    idxs = np.flatnonzero((df_csv[['filename','watyr']].values == name.values).all(axis=1))
    idxs_dt_pre = pre_drain_dt[idxs]
    idxs_dt_post = post_drain_dt[idxs]
        
    # in case there is no idxs_dt_pre or idxs_dt_post
    # (e.g. no draining during water year) then don't change anything in data
    # and keep flag as 0
    corrected_data = data_subset.copy()
    flags = data_subset.copy()*0 # hack to keep array indices but make all vals 0
    flags[np.isnan(flags)] = 0 # make sure there are no nans

    # bring data back up after jumps if there is a drain during water year
    for i in range(len(idxs_dt_pre)):
        
        # if there is no pre jump date in csv (e.g. because the jump is at i-1)
        if pd.isnull(idxs_dt_pre[i]):
            ts_idx_post = int(np.flatnonzero(idxs_dt_post[i] == dt)[0]) if np.any(idxs_dt_post[i] == dt) else None
            jump_val = corrected_data.loc[ts_idx_post-1] - corrected_data.loc[ts_idx_post]
            corrected_data.loc[ts_idx_post:] = corrected_data.loc[ts_idx_post:] + jump_val
            flags.loc[ts_idx_post:] = flag
       
       # if there is no pre jump date in csv (e.g. because the jump is earlier
       # than i-1 and there are nans in between)
        else:
            ts_idx_pre = int(np.flatnonzero(idxs_dt_pre[i] == dt)[0]) if np.any(idxs_dt_pre[i] == dt) else None
            ts_idx_post = int(np.flatnonzero(idxs_dt_post[i] == dt)[0]) if np.any(idxs_dt_post[i] == dt) else None
            jump_val = corrected_data.loc[ts_idx_pre] - corrected_data.loc[ts_idx_post]
            corrected_data.loc[ts_idx_post:] = corrected_data.loc[ts_idx_post:] + jump_val
            flags.loc[ts_idx_post:] = flag
                
    data_all.iloc[corrected_data.index] = corrected_data
    flag_arr.iloc[flags.index] = flags       
    
    return data_all, flag_arr

#%% Detect and fix decreasing trends in PC_Raw_Pipe data which can
# be linked to evaporation
def fix_pc_pipe_evaporation(data_all, data_subset, flag):
    
    # Ensure data_all and data_subset are copies if they are slices of other DataFrames
    data_all = data_all.copy()
    data_subset = data_subset.copy()
    
    flag_arr = pd.Series(np.zeros((len(data_all))))
    
    # create temp array and find nans
    corrected_data = data_subset.copy()    
    nan_idxs = np.flatnonzero(np.isnan(corrected_data))
    
    # prepare timeseries for differentiation step
    first_idx_val = corrected_data.iloc[0]
    corrected_data.iloc[0] = 0 # set zero in case it starts as nan
    corrected_data = corrected_data.interpolate() # interpolate nans to differentiate

    # identify declines in data (negative trends) and remove their impact on 
    # the timeseries. This dampens the trend but keeps the cummulative values
    # realistic. One could alternatively add the negative differences to the
    # the whole timeseries but this results in unrealisticly high cummulative
    # values because sometimes neg trends are compensated by positive trends later    
    rg = np.nanmax(corrected_data) - np.nanmin(corrected_data) # save initial range
    slope_change = np.diff(corrected_data) # differentiate
    slope_change[slope_change < 0] = 0 # reset negative increments to 0
    cum_corrected = np.cumsum([slope_change]) # assemble into cumulative sum again
    cum_corrected[np.isnan(cum_corrected)] = np.nan # reset to NaN values that were originally NaNs
   
    # normalize and scale
    corrected_data.iloc[0:len(cum_corrected)] = cum_corrected / max(cum_corrected) * rg
    corrected_data.iloc[nan_idxs] = np.nan # reset nans for pre-interpolation
    corrected_data.iloc[0] = first_idx_val # reset first index in ts from before
    corrected_data.iloc[-1] = corrected_data.iloc[-1] + abs(corrected_data.iloc[-2]-corrected_data.iloc[-1]) # add diff to last index which was omitted from np.diff earlier
    
    data_all.iloc[corrected_data.index] = np.round(corrected_data,1) # round data
    flag_arr.iloc[corrected_data.index] = flag
    
    return data_all, flag_arr
 
#%%