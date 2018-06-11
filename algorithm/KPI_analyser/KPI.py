import pandas as pd


# These module is minted to collect KPI's from the output of IPLOM and make graphs
def KPI(report, file, path):
    data = pd.read_csv(file)
    data = data.sort_values(by=['log_id', 'cluster'])
    for evt in report:
        for tag in evt['tags']:
            if tag['kpi_score']:
                tmp_log_id = data.log_id[data['cluster'] == int(evt['eventId'])].tolist()
                tmp_log = data.log[data['cluster'] == int(evt['eventId'])].tolist()
                tmp_values = [getKPI(log,tag['tag']) for log in tmp_log]
                tmp_df = pd.DataFrame({'x':tmp_log_id,'y':tmp_values})
                tmp_df.to_csv(path+"/"+evt['eventId']+"_"+tag['tag']+".csv", index=False)




def KPI1(report, file, path):
    KPI = possibleKPIs(report)
    data = pd.read_csv(file)
    for kpi in KPI:
        tmp_log_id = data.log_id[data['cluster'].isin([int(x) for x in KPI[kpi]])].tolist()
        tmp_log = data.log[data['cluster'].isin([int(x) for x in KPI[kpi]])].tolist()
        tmp_values = [getKPI(log,kpi) for log in tmp_log]
        tmp_df = pd.DataFrame({'x':tmp_log_id,'y':tmp_values})
        tmp_df.to_csv(path+"/"+kpi+".csv", index=False)
    return KPI




def possibleKPIs(cl):
    possibleKpi = {}
    for evt in cl:
        for tag in evt['tags']:
            if tag['kpi_score'] > 0:
                if tag['tag'] in possibleKpi:
                    possibleKpi[tag['tag']].append(evt['eventId'])
                else:
                    possibleKpi[tag['tag']] = [evt['eventId']]
    return possibleKpi


def getKPI(log,kpi):
    tmp = log.split()
    value = tmp[tmp.index(kpi)+1]
    if isint(value):
        return int(value)

    if isfloat(value):
        return float(value)
    else:
        return value

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def isint(value):
    try:
        int(value)
        return True
    except ValueError:
        return False