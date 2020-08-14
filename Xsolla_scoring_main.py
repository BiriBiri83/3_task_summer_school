# -*- coding: utf-8 -*-
from google.oauth2 import service_account
import pandas_gbq 

import numpy as np
import pandas as pd
import math as mt
import datetime as dt
import Xsolla_scoring_lib_main as lib_main
import pprint

CREDENTIALS = service_account.Credentials.from_service_account_info({
***
})

first_date = '2018-04-01' # Задаю дату явно, чтобы можно было с ней поиграться
days = 63
periodic = 7
timestart = dt.datetime.strptime(first_date,'%Y-%m-%d').date()

DataFrame = lib_main.getFreshData(CREDENTIALS,'findcsystem')
DataFrame.head(10)

delta = dt.timedelta(days=days) # Хочу взять только агентов, которые работали в эти даты. Остальные только захламляют
assignee_id_unique = DataFrame[(DataFrame["updated"] <= pd.Timestamp(timestart)) & (DataFrame["updated"] >= pd.Timestamp(timestart - delta))]["assignee_id"].unique()

listofonemetric = []
listoftestres = []
listoftestreschan = []
for id in assignee_id_unique: # Цикл по уникальным агентам
    test_user = DataFrame[DataFrame.assignee_id == id][:]
    test_user.reset_index(inplace=True, drop=True)
    if len(test_user) == 0:
        continue
    else:
        test_result = lib_main.workloadScoringByStatuses(test_user, 63, 7, first_date)
        test_result2 = lib_main.workloadScoringByStatusesChan(test_user, 63, 7, first_date)
        listoftestres.append(test_result)
        listoftestreschan.append(test_result2)
        listofonemetric.append(lib_main.OneMetricScore(test_result))
onemetricdf = pd.concat(listofonemetric, ignore_index = True) # Датасет по статусам и каналам
statusesdf = pd.concat(listoftestres, ignore_index = True) # Датасет с одной метрикой
statuseschandf = pd.concat(listoftestreschan, ignore_index = True)

lib_main.insertScoreResultData(statusesdf, onemetricdf, statuseschandf, 'findcsystem','xsolla_summer_school','score_result_status', 'score_result_total', 'score_result_status_channel')