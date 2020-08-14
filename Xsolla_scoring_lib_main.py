# -*- coding: utf-8 -*-
import pandas_gbq
import numpy as np
import pandas as pd
import math as mt
import datetime as dt

"""
Created on Wed Aug 12 20:06:07 2020

@author: 21362
"""

"""[summary]
Funtion for getting fresh data from BigQuery for workload scoring model
[description]
Credentials - google service account object with credentials data for project
SqlQuery - string, sql query for BigQeury database
[example]
Input: Credentials = credentials_object
       SqlQuery = 'select * from dataset_name.table_name'
Output: id	    created_at	        updated_at	        type	  subject   description	                                                                                          status	requester_id	submitter_id   assignee_id	 id_project	 id_invoice	channel	country	 manual_category  auto_category	 subcategory   feedback_score	feedback_comment
	    2520211	2018-02-05 08:59:15	2018-02-23 13:05:39	question	        Credit card payments not working from website.	I have been trying since Thursday 1st of Jan t...	  closed	360790164527	360790164527   20890258907	 21190	     316520736	other	za	     None	          None	         None	       unoffered	    None
        2740781	2018-08-17 01:48:04	2018-09-15 11:00:15	question	        Re: error showed during paid subscription on t...	__________________________________\nType your ... closed	365082895633	951579756	   360133124587	 15174	     367443669	email	za	     None	          None	         None	       offered	        None
"""
def getFreshData(Credentials,ProjectId):
    bigquery_sql = " ".join(["SELECT id, DATE(CAST(created_at AS DATETIME)) AS created, DATE(CAST(updated_at AS DATETIME)) AS updated, status, assignee_id, channel",
                             "FROM `xsolla_summer_school.customer_support`",
                             "WHERE status IN ('closed','solved')",
                             "ORDER BY updated_at"])

    dataframe = pandas_gbq.read_gbq(bigquery_sql,project_id=ProjectId, credentials=Credentials, dialect="standard")

    return dataframe


"""[summary]
Function for scoring workload by statuses (In Progress and Done) and channels for one employee, NumOfAllDays = 63, NumOfIntervalDays = 7
[description]
Data - pandas dataframe object, with hist data for customer support agent
NumOfAllDays - integer, number of days for all hist data
NumOfIntervalDays - integer, number of days for weekly calculating interval
current_date - str like ('yyyy-mm-dd'), date from which need to count employee metrics
[example]
Input: Data = id	   created	   updated	   status	assignee_id
              2936149  2018-12-31  2019-01-30  closed	26979706288
              2936171  2018-12-31  2019-01-30  closed	26979706288
       NumOfAllDays = 63
       NumOfIntervalDays = 7
       current_date = '2018-04-01'      
Output: assignee_id	       status	count_last_period	count_mean_calc_period	count_sem_calc_period	score_value
0	    12604869947	       closed	15	                12.62	                1.64	                 2
1	    12604869947	       solved	23	                32.25	                7.45	                 0

The function takes pandas dataframe object and groupes it by statuses and channels. 
Then it counts number of request "id"s by periods with length {NumOfIntervalDays} back to {NumOfAllDays} from the {current_date}.
Here the last {NumOfIntervalDays} is current period to compare.
Next step is calculatig dispertion of "id"s for all periods except last one, and then we have standard deviation and standard error. 
It uses the standard error for calculating borders of confidence interval. Then it use these borders to scoring support agents
by "0", "1", "2" number from lowest to highest overload. Returns pandas dataframe with metrics and scores.
""" 
def workloadScoringByStatusesChan(Data, NumOfAllDays, NumOfIntervalDays, current_date):
    assignee_id = np.unique(Data.assignee_id)
    assignee_id = assignee_id[0]
    
    #splitting by status
    statuses = np.unique(Data.status)
    channels = Data["channel"].dropna().unique() # Уникальные каналы
    assignee_id_list = []
    status_list = []
    channel_list = []
    avg_num_of_task_per_week_list = []
    ste_list = []
    num_tasks_per_current_week_list = []
    score_for_status_list = []
    for status in statuses:
        for chan in channels:
            dataframe_status = Data[(Data.status == str(status))][:]
            dataframe_channel = dataframe_status[(dataframe_status["channel"] == str(chan))]
        
            #time borders params
            curr_date = dt.datetime.strptime(current_date,'%Y-%m-%d')
            curr_date = curr_date.date()
            delta = dt.timedelta(days=NumOfAllDays)
            first_date = curr_date-delta
        
            #time interval params
            delta_interval = dt.timedelta(days=NumOfIntervalDays)
            first_interval = first_date+delta_interval
                
            num_of_intervals = int(NumOfAllDays/NumOfIntervalDays)
            num_tasks_per_week = []
            for i in range(0,num_of_intervals):
                #interval = dataframe_status[(dataframe_status.updated >= str(first_date)) & (dataframe_status.updated <= str(first_interval))][:]
                interval = dataframe_channel[(dataframe_channel.updated >= str(first_date)) & (dataframe_channel.updated <= str(first_interval))][:]
                #interval_chan = dataframe_channel[(dataframe_channel.updated >= str(first_date)) & (dataframe_channel.updated <= str(first_interval))][:]
                first_date = first_date + delta_interval
                first_interval = first_interval + delta_interval
        
                if i != (num_of_intervals-1):        
                    num_of_tasks = len(np.unique(interval['id']))
                    #num_of_tasks_chan = len(np.unique(interval_chan['id']))
                    num_tasks_per_week.append(num_of_tasks) #history number of tasks
                    #num_tasks_per_week_chan.append(num_of_tasks) #history number of tasks
                else:
                    num_tasks_per_current_week = len(np.unique(interval['id'])) #currently number of tasks
            
            #avg_num_of_task_per_week = round(np.mean(num_tasks_per_week),2)
            avg_num_of_task_per_week = round(np.median(num_tasks_per_week), 2) # Попробуем медиану
            #squared deviations
            x_values = []
            for num in num_tasks_per_week:
                x = round((num - avg_num_of_task_per_week)**2, 2)
                x_values.append(x)
    
            #data sampling statistics
            x_sum = round(sum(x_values), 2) #sum of squared deviations
            dispersion = round(x_sum/(num_of_intervals-1), 2) #dispersion
            std = round(mt.sqrt(dispersion), 2) #standart deviation for sample
            ste = round(std/mt.sqrt(num_of_intervals), 2) #standart error for sample
            #stdpand = np.asarray(num_tasks_per_week).std()
    
            #confidence interval
            left_border = int(avg_num_of_task_per_week - ste) 
            right_border = int(avg_num_of_task_per_week + ste)
            
            #left_border = int(avg_num_of_task_per_week - 2*std) # большие значения стандартного отклонения. Не применительно в рамках задачи
            #right_border = int(avg_num_of_task_per_week + 2*std)
    
            #workload scoring for status
            score_for_status = workloadScoreStatuses(left_border,right_border,num_tasks_per_current_week)        
            assignee_id_list.append(assignee_id)
            status_list.append(status)
            channel_list.append(chan)
            avg_num_of_task_per_week_list.append(avg_num_of_task_per_week)
            ste_list.append(ste)
            num_tasks_per_current_week_list.append(num_tasks_per_current_week)
            score_for_status_list.append(score_for_status)
            
        score_data = {"assignee_id":assignee_id_list,"status":status_list,
                      "channel":channel_list,
                      "count_last_period":num_tasks_per_current_week_list,
                      "count_mean_calc_period":avg_num_of_task_per_week_list,
                      "count_sem_calc_period":ste_list,
                      "score_value":score_for_status_list}
        scores = pd.DataFrame(data=score_data)

    return scores

"""[summary]
Function for scoring workload by statuses (In Progress and Done) for one employee, NumOfAllDays = 63, NumOfIntervalDays = 7
[description]
Data - pandas dataframe object, with hist data for customer support agent
NumOfAllDays - integer, number of days for all hist data
NumOfIntervalDays - integer, number of days for weekly calculating interval
[example]
Input: Data = id	   created	   updated	   status	assignee_id
              2936149  2018-12-31  2019-01-30  closed	26979706288
              2936171  2018-12-31  2019-01-30  closed	26979706288
       NumOfAllDays = 63
       NumOfIntervalDays = 7
Output: assignee_id	 status	 count_last_period	count_mean_calc_period	count_sem_calc_period	score_value
        12604869947	 closed	 196	            196.62	                9.43	                1
        12604869947	 solved	 0	                0.00	                0.00	                0    
"""
def workloadScoringByStatuses(Data, NumOfAllDays, NumOfIntervalDays, current_date):
    assignee_id = np.unique(Data.assignee_id)
    assignee_id = assignee_id[0]
    
    #splitting by status
    statuses = np.unique(Data.status)
    assignee_id_list = []
    status_list = []
    avg_num_of_task_per_week_list = []
    ste_list = []
    num_tasks_per_current_week_list = []
    score_for_status_list = []
    for status in statuses:
        dataframe_status = Data[(Data.status == str(status))][:]
    
        #time borders params
        curr_date = dt.datetime.strptime(current_date,'%Y-%m-%d')
        curr_date = curr_date.date()
        delta = dt.timedelta(days=NumOfAllDays)
        first_date = curr_date-delta
    
        #time interval params
        delta_interval = dt.timedelta(days=NumOfIntervalDays)
        first_interval = first_date+delta_interval
            
        num_of_intervals = int(NumOfAllDays/NumOfIntervalDays)
        num_tasks_per_week = []
        for i in range(0,num_of_intervals):
            interval = dataframe_status[(dataframe_status.updated >= str(first_date)) & (dataframe_status.updated <= str(first_interval))][:]
            first_date = first_date + delta_interval
            first_interval = first_interval + delta_interval
    
            if i != (num_of_intervals-1):        
                num_of_tasks = len(np.unique(interval['id']))
                num_tasks_per_week.append(num_of_tasks) #history number of tasks
            else:
                num_tasks_per_current_week = len(np.unique(interval['id'])) #currently number of tasks
        
        avg_num_of_task_per_week = round(np.mean(num_tasks_per_week),2)

        #squared deviations
        x_values = []
        for num in num_tasks_per_week:
            x = round((num - avg_num_of_task_per_week)**2,2)
            x_values.append(x)

        #data sampling statistics
        x_sum = round(sum(x_values),2) #sum of squared deviations
        dispersion = round(x_sum/(num_of_intervals-1),2) #dispersion
        std = round(mt.sqrt(dispersion),2) #standart deviation for sample
        ste = round(std/mt.sqrt(num_of_intervals),2) #standart error for sample

        #confidence interval
        left_border = int(avg_num_of_task_per_week - ste) # Задать вопрос
        right_border = int(avg_num_of_task_per_week + ste)

        #workload scoring for status
        score_for_status = workloadScoreStatuses(left_border,right_border,num_tasks_per_current_week)        
        assignee_id_list.append(assignee_id)
        status_list.append(status)
        avg_num_of_task_per_week_list.append(avg_num_of_task_per_week)
        ste_list.append(ste)
        num_tasks_per_current_week_list.append(num_tasks_per_current_week)
        score_for_status_list.append(score_for_status)
        
    score_data = {"assignee_id":assignee_id_list,"status":status_list,
                  "count_last_period":num_tasks_per_current_week_list,
                  "count_mean_calc_period":avg_num_of_task_per_week_list,
                  "count_sem_calc_period":ste_list,
                  "score_value":score_for_status_list}
    scores = pd.DataFrame(data=score_data)

    return scores


"""[summary]
Function for scoring workload for current status
[description]
LeftBoard - float, left boarder for confidence interval
RightBoard - float right boarder for confidence interval
CurrentNumOfTasks - integer, number of customer support agent tasks for current interval (7 days)
[example]
Input: LeftBoard = 187
       RightBoard = 206
       CurrentNumOfTasks = 196
Output: 1

If all metrics is 0 then agent didnt work that period or absolutely free, score is "0";
If agent has some tasks but its number less than lower border then he is free and can do more task than he do. Score is "0".
If agent's number of task in confidence interval then he doing well.
If agent's number of task more than higher border of confidence interval then he hightly overloaded.
"""
def workloadScoreStatuses(LeftBoard,RightBoard,CurrentNumOfTasks):
    if (LeftBoard == 0) & (CurrentNumOfTasks == 0) & (RightBoard == 0):
        score = 0
    elif (CurrentNumOfTasks >= 0) & (CurrentNumOfTasks < LeftBoard):
        score = 0
    elif (CurrentNumOfTasks >= LeftBoard) & (CurrentNumOfTasks <= RightBoard):
        score = 1
    else:
        score = 2
    
    return score


"""[summary]
Function for creating "one-metric-score" from scoring by statuses.
[description]
DF - pandas dataframe. It's an output of function "workloadScoringByStatuses".
[example]
Input: assignee_id    status  ... score_value
     0 21627434567    closed  ...     1
     1 21627434567    solved  ...     2
     
Output: assignee_id      score_value
    0   21627434567           2

If sum of scores by statuses "closed" and "solved" is greater than or equal to 3 or score by status "solved" is 2 then agent is overloaded. Score is "2".
If sum of scores by statuses "closed" and "solved" is greater than or equal to 2 and score by status "solved" is equal to 1 then agent is doing great. Score is "1".
Else sum of scores by statuses "closed" and "solved" less than 2 and score by status "solved" equal to 0 then agents is free or doing nothing. Score is "0".
"""
def OneMetricScore(DF):
    if len(DF[DF["status"] == "solved"]) == 0:
        solvedscore = 0
        closedscore = int(DF[DF["status"] == "closed"]["score_value"].tolist()[0]) 
        newscore = closedscore
    else:
        newscore = int(DF[DF["status"] == "solved"]["score_value"].tolist()[0]) + int(DF[DF["status"] == "closed"]["score_value"].tolist()[0])
        solvedscore = int(DF[DF["status"] == "solved"]["score_value"].tolist()[0])
        closedscore = int(DF[DF["status"] == "closed"]["score_value"].tolist()[0]) 
    
    if newscore >= 3 or solvedscore == 2:
        metricscore = 2
    elif newscore >= 2 and newscore < 4 and solvedscore == 1:
        metricscore = 1
    else:
        metricscore = 0
    newDF = pd.DataFrame()
    newDF["assignee_id"] = DF[DF["status"] == "solved"]["assignee_id"]
    newDF["score_value"] = metricscore
    return newDF
    

"""[summary]
Function for inserting data to BigQuery database
[description]
InsertDataFrame - pandas dtaframe object, with score result data by statuses
InsertDataFrameTotal - pandas dtaframe object, with total score
ProjectId - string, name of project in google cloud platform 
DatasetId - string, name of dataset in bigquery for raw data
TableId - string, name of table for InsertDataFrame data
TableId2 - string, name of table for InsertDataFrameTotal data
[example]
Input: InsertDataFrame = assignee_id	status	count_last_period	count_mean_calc_period	count_sem_calc_period	score_value
                         11527290367	closed	163	                140.38	                12.4	                2
                         11527290367	solved	0	                0.00	                0.0 	                0
                         
  InsertDataFrameTotal = assignee_id	score_value
                         11527290367	      1
                         11527290367	      0                  
       ProjectId = 'test-gcp-project'
       DatasetId = 'test_dataset'
       TableId = 'test_table'
       TableId2 = 'test_table2'
"""
def insertScoreResultData(InsertDataFrame, InsertDataFrameTotal, InsertDataFrameChan, ProjectId, DatasetId, TableId, TableId2, TableId3):
    destination_table = f"{DatasetId}.{TableId}"
    destination_table2 = f"{DatasetId}.{TableId2}"
    destination_table3 = f"{DatasetId}.{TableId3}"
    
    res_df_stat = pd.DataFrame()
    res_df_stat['assignee_id'] = InsertDataFrame['assignee_id'].astype('int64')
    res_df_stat['status'] = InsertDataFrame['status'].astype('str')
    res_df_stat['count_last_period'] = InsertDataFrame['count_last_period'].astype('int')
    res_df_stat['count_mean_calc_period'] = InsertDataFrame['count_mean_calc_period'].astype('float')
    res_df_stat['count_sem_calc_period'] = InsertDataFrame['count_sem_calc_period'].astype('float')
    res_df_stat['score_value'] = InsertDataFrame['score_value'].astype('int')
    res_df_stat['developer'] = 'K. Pischalnikov'
    res_df_stat['developer'] = res_df_stat['developer'].astype('str')
    
    
    res_df = pd.DataFrame()
    res_df['assignee_id'] = InsertDataFrameChan['assignee_id'].astype('int64')
    res_df['status'] = InsertDataFrameChan['status'].astype('str')
    res_df['count_last_period'] = InsertDataFrameChan['count_last_period'].astype('int')
    res_df['count_mean_calc_period'] = InsertDataFrameChan['count_mean_calc_period'].astype('float')
    res_df['count_sem_calc_period'] = InsertDataFrameChan['count_sem_calc_period'].astype('float')
    res_df['score_value'] = InsertDataFrameChan['score_value'].astype('int')
    res_df['developer'] = 'K. Pischalnikov'
    res_df['developer'] = res_df['developer'].astype('str')
    res_df['channel'] = InsertDataFrameChan['channel'].astype('str')
    
    res_df_total = pd.DataFrame()
    res_df_total['assignee_id'] = InsertDataFrameTotal['assignee_id'].astype('int64')
    res_df_total['score_value'] = InsertDataFrameTotal['score_value'].astype('float')
    res_df_total['developer'] = 'K. Pischalnikov'
    res_df_total['developer'] = res_df['developer'].astype('str')
    print(res_df_stat)
    print(res_df)
    print(res_df_total)
    pandas_gbq.to_gbq(res_df_stat, destination_table=destination_table, project_id=ProjectId, if_exists='append')
    pandas_gbq.to_gbq(res_df_total, destination_table=destination_table2, project_id=ProjectId, if_exists='append')
    pandas_gbq.to_gbq(res_df, destination_table=destination_table3, project_id=ProjectId, if_exists='append')