import copy
import sys
import time
import os
import gc
import re
from collections import Counter
import csv
import datetime
import copy
import pandas as pd
import numpy as np

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




class Partition:
    """
	Wrap around the logs and the step number
	"""

    def __init__(self, stepNo, numOfLogs=0, lenOfLogs=0):
        self.logLL = []
        self.stepNo = stepNo
        self.valid = True
        self.numOfLogs = numOfLogs
        self.lenOfLogs = lenOfLogs


class Event:
    eventId = 1

    def __init__(self, eventStr):
        self.eventStr = eventStr
        self.eventId = Event.eventId
        self.eventCount = 0
        Event.eventId += 1


class Para:
    """
    maxEventLen: the length of the longest log/event, which is used in step 1 to split logs into partitions according to their length
    path: the path of the input file
    step2Support: the support threshold to create a new partition, partitions which contains less than step2Support logs will not go through step 2
    PST: Partition support ratio threshold
    CT: Cluster goodness threshold used in DetermineP1P2 in step3. If the columns with unique term more than CT, we skip step 3
    """

    def __init__(self, path='../Data/2kProxifier/', logname='rawlog.log', savePath='./results_2kProxifier/',
                 saveFileName = 'template', maxEventLen = 120, step2Support = 0, PST = 0.0,
                 CT=0.35, lowerBound=0.25, upperBound=0.9, usePST=False,
                 removable=True, removeCol=[0, 1, 2, 3, 4], regular=True,
                 rex=['blk_(|-)[0-9]+', '(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)'],
                 line_starter=None, remove_chars=None, first_line=1, last_line=None,
                 transform_chars=None, get_stars=None):
        self.maxEventLen = maxEventLen
        self.path = path
        self.logname = logname
        self.savePath = savePath
        self.saveFileName = saveFileName
        self.step2Support = step2Support
        self.PST = PST
        self.CT = CT
        self.lowerBound = lowerBound
        self.upperBound = upperBound
        self.usePST = usePST
        self.removable = removable
        self.removeCol = removeCol
        self.regular = regular
        self.rex = rex
        self.line_starter = line_starter
        self.remove_chars = remove_chars
        self.first_line = first_line
        self.last_line = last_line
        self.transform_chars = transform_chars
        self.get_stars= get_stars


class IPLoM:

    def __init__(self, para):
        self.para = para
        self.partitionsL = []
        self.eventsL = []
        self.output = []
        self.logs = []
        self.timestamps = []

        # Initialize some partitions which contain logs with different length
        for logLen in range(self.para.maxEventLen + 1):
            self.partitionsL.append(Partition(stepNo=1, numOfLogs=0, lenOfLogs=logLen))

    def splitProcess(self, report, toSplit):
        print("further splitting")
        global l
        t1 = time.time()
        print("Open file")
        f_in = pd.read_csv(self.para.path)
        startId = int(max(f_in.cluster))
        self.logs = f_in.loc[f_in['cluster'] == int(toSplit)].log.tolist()

        # Get fixed tags
        fixedTags = list(np.array(self.logs[0].split())[self.para.removeCol])
        fixedTags = list(zip(self.para.removeCol, fixedTags))

        print("Step1")
        self.Step1()
        print("Step2")
        self.Step2()
        print("Step3")
        self.Step3()
        print("Step4")
        self.Step4()
        print("getOutput")
        self.getOutput()

        t2 = time.time()

        print("Write modifications to file")
        # Updating stars: ok
        stars = None
        if self.para.get_stars:
            stars = self.getStarsSplitingProcess()
            stars = dict((k+startId, v) for k, v in stars.items())
            del report["stars"][toSplit]
            report["stars"].update(stars)

        # Creating report: ok
        res = self.getReport(add=startId)
        for evt in res:
            for tag in fixedTags:
                evt["tags"].insert(tag[0], tag[1])
        # Detecting KPIs
        self.detect_kpi(res, stars)

        # Updating results: ok
        toDelete = (idx for idx,item in enumerate(report["report"]) if item["eventId"] == toSplit).__next__()
        del report["report"][toDelete]
        report["report"][toDelete:toDelete] = res

        # Updating output file: not yet
        self.output = [[ int(el[0])]+[ int(el[1]) + startId]+el[2:] for el in self.output]
        tmp = pd.DataFrame(self.output)
        tmp = tmp.sort_values(by=0)
        f_in.cluster[f_in.cluster == int(toSplit)] = tmp[1].tolist()
        f_in.to_csv(self.para.path, index=False)

        print('this process takes', t2 - t1)
        print('*********************************************')
        gc.collect()
        Event.eventId = 1
        report['time'] = t2 - t1
        return report

    def mainProcess(self):
        global l
        t1 = time.time()
        print("preprocess")
        self.preprocess()
        print("Step1")
        self.Step1()
        print("Step2")
        self.Step2()
        print("Step3")
        self.Step3()
        print("Step4")
        self.Step4()
        print("getOutput")
        self.getOutput()
        t2 = time.time()
        if not os.path.exists(self.para.savePath + self.para.saveFileName):
            os.makedirs(self.para.savePath + self.para.saveFileName)
        # TODO: delete the else for the final version
        #else:
        #    self.deleteAllFiles(self.para.savePath + self.para.saveFileName)

        print("WriteLogWithEventID")
        full_path = self.WriteLogWithEventID(self.para.savePath + self.para.saveFileName)
        #self.WriteLogs(self.para.savePath + self.para.saveFileName)

        stars = None
        if self.para.get_stars:
            stars = self.getStars()

        res = self.getReport()

        self.detect_kpi(res, stars)
        print(res)
        print('this process takes', t2 - t1)
        print('*********************************************')
        gc.collect()
        Event.eventId = 1
        return {'time': t2 - t1, 'report': res , 'stars':stars, 'full_path':full_path}

    def preprocess(self):
        logfile = open(self.para.path, "r")
        f_in = logfile.read()
        print("file loaded")

        ## Detect lines in the file ! and save them to a list ##
        if (self.para.line_starter != "None"):
            print("line starter detected")
            line_starter_pos = [m for m in re.finditer(self.para.line_starter, f_in)]
            for i, r in enumerate(line_starter_pos):
                label = 'None'
                try:
                    end = line_starter_pos[i + 1].start()
                except:
                    end = len(f_in)
                self.timestamps.append(f_in[r.start():r.end()])
                txt = f_in[r.start(): end - 1].replace('\n', ' ')
                self.logs.append(txt)
        else:
            print("line starter not detected")
            self.logs = f_in.split('\n')

        self.logs = self.logs[self.para.first_line:self.para.last_line]
        logfile.close()

        if self.para.transform_chars:
            for k,v in self.para.transform_chars:
                self.logs = [re.sub(k,v, log) for log in self.logs]


        ## Delete special expressions ##

        if self.para.regular:
            self.logs = [re.sub("|".join(self.para.rex), '', log) for log in self.logs]

        ## Replace each char with a white space ##
        if (self.para.remove_chars):
            self.logs = [re.sub("|".join(self.para.remove_chars), ' ', log) for log in self.logs]



    def Step1(self):
        lineCount = 1
        for line in self.logs:
            # If line is empty, skip
            if line.strip() == "":
                continue

            wordSeq = line.strip().split('\t')[0].split()
            if self.para.removable:
                wordSeq = [word for i, word in enumerate(wordSeq) if i not in self.para.removeCol]

            # Generate terms list, with ID in the end
            wordSeq.append(str(lineCount))
            # print (wordSeq)
            lineCount += 1
            # if lineCount%100 == 0:
            # 	print(lineCount)

            # Add current log to the corresponding partition
            self.partitionsL[len(wordSeq) - 1].logLL.append(wordSeq)
            self.partitionsL[len(wordSeq) - 1].numOfLogs += 1
        self.logs = None

        for partition in self.partitionsL:
            if partition.numOfLogs == 0:
                partition.valid = False

            elif self.para.usePST and 1.0 * partition.numOfLogs / lineCount < self.para.PST:
                for logL in partition.logLL:
                    self.partitionsL[0].logLL.append(logL)
                    self.partitionsL[0].numOfLogs += 1
                partition.valid = False

    def Step2(self):

        for partition in self.partitionsL:

            if not partition.valid:
                continue

            if partition.numOfLogs <= self.para.step2Support:
                continue

            # Avoid going through newly generated partitions
            if partition.stepNo == 2:
                break

            uniqueTokensCountLS = []
            for columnIdx in range(partition.lenOfLogs):
                uniqueTokensCountLS.append(set())

            for logL in partition.logLL:
                for columnIdx in range(partition.lenOfLogs):
                    uniqueTokensCountLS[columnIdx].add(logL[columnIdx])

            # Find the column with minimum unique tokens
            minColumnIdx = 0
            minColumnCount = len(uniqueTokensCountLS[0])

            for columnIdx in range(partition.lenOfLogs):
                if minColumnCount > len(uniqueTokensCountLS[columnIdx]):
                    minColumnCount = len(uniqueTokensCountLS[columnIdx])
                    minColumnIdx = columnIdx

            # If there is one column with one unique term, do not split this partition
            if minColumnCount == 1:
                continue

            # From split-token to log list
            logDLL = {}
            for logL in partition.logLL:
                if logL[minColumnIdx] not in logDLL:
                    logDLL[logL[minColumnIdx]] = []
                logDLL[logL[minColumnIdx]].append(logL)

            for key in logDLL:
                if self.para.usePST and 1.0 * len(logDLL[key]) / partition.numOfLogs < self.para.PST:
                    self.partitionsL[0].logLL += logDLL[key]
                    self.partitionsL[0].numOfLogs += len(logDLL[key])
                else:
                    newPartition = Partition(stepNo=2, numOfLogs=len(logDLL[key]), lenOfLogs=partition.lenOfLogs)
                    newPartition.logLL = logDLL[key]
                    self.partitionsL.append(newPartition)

            partition.valid = False

    def Step3(self):

        for partition in self.partitionsL:

            if not partition.valid:
                continue

            if partition.stepNo == 3:
                break

            # Debug
            # print ("*******************************************")
            # print ("Step 2 Partition:")
            # print ("*******************************************")
            # for logL in partition.logLL:
            # 	print (' '.join(logL))

            # Find two columns that my cause split in this step
            p1, p2 = self.DetermineP1P2(partition)

            if p1 == -1 or p2 == -1:
                continue

            try:

                p1Set = set()
                p2Set = set()
                mapRelation1DS = {}
                mapRelation2DS = {}

                # Construct token sets for p1 and p2, dictionary to record the mapping relations between p1 and p2
                for logL in partition.logLL:
                    p1Set.add(logL[p1])
                    p2Set.add(logL[p2])

                    if (logL[p1] == logL[p2]):
                        print("!!  p1 may be equal to p2")

                    if logL[p1] not in mapRelation1DS:
                        mapRelation1DS[logL[p1]] = set()
                    mapRelation1DS[logL[p1]].add(logL[p2])

                    if logL[p2] not in mapRelation2DS:
                        mapRelation2DS[logL[p2]] = set()
                    mapRelation2DS[logL[p2]].add(logL[p1])

                # originp1S = copy.deepcopy(p1Set)
                # originp2S = copy.deepcopy(p2Set)

                # Construct sets to record the tokens in 1-1, 1-M, M-1 relationships, the left-tokens in p1Set & p2Set are in M-M relationships
                oneToOneS = set()
                oneToMP1D = {}
                oneToMP2D = {}

                # select 1-1 and 1-M relationships
                for p1Token in p1Set:
                    if len(mapRelation1DS[p1Token]) == 1:
                        if len(mapRelation2DS[list(mapRelation1DS[p1Token])[0]]) == 1:
                            oneToOneS.add(p1Token)

                    else:
                        isOneToM = True

                        for p2Token in mapRelation1DS[p1Token]:
                            if len(mapRelation2DS[p2Token]) != 1:
                                isOneToM = False
                                break
                        if isOneToM:
                            oneToMP1D[p1Token] = 0

                # delete the tokens which are picked to 1-1 and 1-M relationships from p1Set, so that the left are M-M
                for deleteToken in oneToOneS:
                    p1Set.remove(deleteToken)
                    p2Set.remove(list(mapRelation1DS[deleteToken])[0])

                for deleteToken in oneToMP1D:
                    for deleteTokenP2 in mapRelation1DS[deleteToken]:
                        p2Set.remove(deleteTokenP2)
                    p1Set.remove(deleteToken)

                # select M-1 relationships
                for p2Token in p2Set:
                    if len(mapRelation2DS[p2Token]) != 1:
                        isOneToM = True
                        for p1Token in mapRelation2DS[p2Token]:
                            if len(mapRelation1DS[p1Token]) != 1:
                                isOneToM = False
                                break
                        if isOneToM:
                            oneToMP2D[p2Token] = 0

                # delete the tokens which are picked to M-1 relationships from p2Set, so that the left are M-M
                for deleteToken in oneToMP2D:
                    p2Set.remove(deleteToken)
                    for deleteTokenP1 in mapRelation2DS[deleteToken]:
                        p1Set.remove(deleteTokenP1)

                # calculate the #Lines_that_match_S
                for logL in partition.logLL:
                    if logL[p1] in oneToMP1D:
                        oneToMP1D[logL[p1]] += 1

                    if logL[p2] in oneToMP2D:
                        oneToMP2D[logL[p2]] += 1

            except KeyError as er:

                print(er)

                print('erreur: ' + str(p1) + '\t' + str(p2))

            newPartitionsD = {}
            if partition.stepNo == 2:
                newPartitionsD["dumpKeyforMMrelationInStep2__"] = Partition(stepNo=3, numOfLogs=0,
                                                                            lenOfLogs=partition.lenOfLogs)
            # Split partition
            for logL in partition.logLL:
                # If is 1-1
                if logL[p1] in oneToOneS:
                    if logL[p1] not in newPartitionsD:
                        newPartitionsD[logL[p1]] = Partition(stepNo=3, numOfLogs=0, lenOfLogs=partition.lenOfLogs)
                    newPartitionsD[logL[p1]].logLL.append(logL)
                    newPartitionsD[logL[p1]].numOfLogs += 1

                # This part can be improved. The split_rank can be calculated once.
                # If is 1-M
                elif logL[p1] in oneToMP1D:
                    # print ('1-M: ' + str(len( mapRelation1DS[logL[p1]] )) + str(oneToMP1D[logL[p1]]))
                    split_rank = self.Get_Rank_Posistion(len(mapRelation1DS[logL[p1]]), oneToMP1D[logL[p1]], True)
                    # print ('result: ' + str(split_rank))
                    if split_rank == 1:
                        if logL[p1] not in newPartitionsD:
                            newPartitionsD[logL[p1]] = Partition(stepNo=3, numOfLogs=0, lenOfLogs=partition.lenOfLogs)
                        newPartitionsD[logL[p1]].logLL.append(logL)
                        newPartitionsD[logL[p1]].numOfLogs += 1
                    else:
                        if logL[p2] not in newPartitionsD:
                            newPartitionsD[logL[p2]] = Partition(stepNo=3, numOfLogs=0, lenOfLogs=partition.lenOfLogs)
                        newPartitionsD[logL[p2]].logLL.append(logL)
                        newPartitionsD[logL[p2]].numOfLogs += 1

                # If is M-1
                elif logL[p2] in oneToMP2D:
                    # print ('M-1: ' + str(len( mapRelation2DS[logL[p2]] )) + str(oneToMP2D[logL[p2]]))
                    split_rank = self.Get_Rank_Posistion(len(mapRelation2DS[logL[p2]]), oneToMP2D[logL[p2]], False)
                    # print ('result: ' + str(split_rank))
                    if split_rank == 1:
                        if logL[p1] not in newPartitionsD:
                            newPartitionsD[logL[p1]] = Partition(stepNo=3, numOfLogs=0, lenOfLogs=partition.lenOfLogs)
                        newPartitionsD[logL[p1]].logLL.append(logL)
                        newPartitionsD[logL[p1]].numOfLogs += 1
                    else:
                        if logL[p2] not in newPartitionsD:
                            newPartitionsD[logL[p2]] = Partition(stepNo=3, numOfLogs=0, lenOfLogs=partition.lenOfLogs)
                        newPartitionsD[logL[p2]].logLL.append(logL)
                        newPartitionsD[logL[p2]].numOfLogs += 1

                # M-M
                else:
                    if partition.stepNo == 2:
                        newPartitionsD["dumpKeyforMMrelationInStep2__"].logLL.append(logL)
                        newPartitionsD["dumpKeyforMMrelationInStep2__"].numOfLogs += 1
                    else:
                        if len(p1Set) < len(p2Set):
                            if logL[p1] not in newPartitionsD:
                                newPartitionsD[logL[p1]] = Partition(stepNo=3, numOfLogs=0,
                                                                     lenOfLogs=partition.lenOfLogs)
                            newPartitionsD[logL[p1]].logLL.append(logL)
                            newPartitionsD[logL[p1]].numOfLogs += 1
                        else:
                            if logL[p2] not in newPartitionsD:
                                newPartitionsD[logL[p2]] = Partition(stepNo=3, numOfLogs=0,
                                                                     lenOfLogs=partition.lenOfLogs)
                            newPartitionsD[logL[p2]].logLL.append(logL)
                            newPartitionsD[logL[p2]].numOfLogs += 1

            if "dumpKeyforMMrelationInStep2__" in newPartitionsD and newPartitionsD[
                "dumpKeyforMMrelationInStep2__"].numOfLogs == 0:
                newPartitionsD["dumpKeyforMMrelationInStep2__"].valid = False
            # Add all the new partitions to collection
            for key in newPartitionsD:
                if self.para.usePST and 1.0 * newPartitionsD[key].numOfLogs / partition.numOfLogs < self.para.PST:
                    self.partitionsL[0].logLL += newPartitionsD[key].logLL
                    self.partitionsL[0].numOfLogs += newPartitionsD[key].numOfLogs
                else:
                    self.partitionsL.append(newPartitionsD[key])

            partition.valid = False

    def Step4(self):
        self.partitionsL[0].valid = False
        if not self.para.usePST and self.partitionsL[0].numOfLogs != 0:
            event = Event(['Outlier'])
            event.eventCount = self.partitionsL[0].numOfLogs
            self.eventsL.append(event)

            for logL in self.partitionsL[0].logLL:
                logL.append(str(event.eventId))

        for partition in self.partitionsL:
            if not partition.valid:
                continue

            if partition.numOfLogs == 0:
                print(str(partition.stepNo) + '\t')

            uniqueTokensCountLS = []
            for columnIdx in range(partition.lenOfLogs):
                uniqueTokensCountLS.append(set())

            for logL in partition.logLL:
                for columnIdx in range(partition.lenOfLogs):
                    uniqueTokensCountLS[columnIdx].add(logL[columnIdx])

            e = copy.deepcopy(partition.logLL[0])[:partition.lenOfLogs]
            for columnIdx in range(partition.lenOfLogs):
                if len(uniqueTokensCountLS[columnIdx]) == 1:
                    continue
                else:
                    e[columnIdx] = '*'
            event = Event(e)
            event.eventCount = partition.numOfLogs

            self.eventsL.append(event)

            for logL in partition.logLL:
                logL.append(str(event.eventId))

    def getOutput(self):
        if not self.para.usePST and self.partitionsL[0].numOfLogs != 0:
            for logL in self.partitionsL[0].logLL:
                self.output.append(logL[-2:] + logL[:-2])
        for partition in self.partitionsL:
            if not partition.valid:
                continue
            for logL in partition.logLL:
                self.output.append(logL[-2:] + logL[:-2])

    def getReport(self,add=0):
        res = []
        for event in self.eventsL:
            part = [L for L in self.output if L[1] == str(event.eventId)]
            res.append({"eventId": str(event.eventId+add), "tags": event.eventStr, "size": len(part)})
        return res

    def detect_kpi(self, data, stars):
        for cl in data:
            for idx, tag in enumerate(cl["tags"]):

                cl["tags"][idx] = {"tag": tag}
                if (idx + 1) == len(cl["tags"]) or tag == "*" or isfloat(tag):
                    cl["tags"][idx]["kpi_score"] = 0
                    continue

                if tag.count(":")>1 or tag.count(",") > 0:
                    cl["tags"][idx]["kpi_score"] = 0
                    continue

                if cl["tags"][idx+1] == "*":
                    if isfloat(stars[int(cl['eventId'])][idx+1][0][0]) or isint(stars[int(cl['eventId'])][idx+1][0][0]):
                        cl["tags"][idx]["kpi_score"] = 1
                    else:
                        cl["tags"][idx]["kpi_score"] = 0
                else:

                    if isfloat(cl["tags"][idx+1]):
                        cl["tags"][idx]["kpi_score"] = 1
                        cl["tags"][idx]["kpi_type"] = "float"
                    elif isint(cl["tags"][idx+1]):
                        cl["tags"][idx]["kpi_score"] = 1
                        cl["tags"][idx]["kpi_type"] = "int"
                    else :
                        cl["tags"][idx]["kpi_score"] = 0


    def getStars(self, add=10):
        stars = {event.eventId : { idx:None for idx, val in enumerate(event.eventStr) if val =="*" } for event in self.eventsL}
        for c in stars:
            for star in stars[c]:
                cnt = Counter([l[int(star) + 2] for l in self.output if (int(l[1]) == c)])
                stars[c][star] = cnt.most_common(10)
        return stars

    def getStarsSplitingProcess(self):

        def getIdx(id):
            for k in self.para.removeCol:
                if(id >= k):
                    id +=1
            return id

        stars = {event.eventId : { idx:None for idx, val in enumerate(event.eventStr) if val =="*" } for event in self.eventsL}
        for c in stars:
            for star in stars[c]:
                cnt = Counter([l[int(star) + 2] for l in self.output if (int(l[1]) == c)])
                stars[c][star] = cnt.most_common(10)
            stars[c] = dict((getIdx(key), value) for (key, value) in stars[c].items())
        return stars

    def WriteLogWithEventID(self, outputPath):
        full_path = outputPath+"Events_"+datetime.datetime.now().strftime('%Y_%m_%d__%H_%M')+".csv"
        log_list = [[log[1], log[0], str(" ".join(log[2:]))] for log in self.output]
        with open(full_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["cluster", "log_id", "log"])
            writer.writerows(log_list)
        return full_path


    def WriteLogWithEventIDAndTimestamp(self, outputPath):
        log_list = [[log[1], log[0], self.timestamps[int(log[0])]] for log in self.output]
        with open(outputPath+datetime.datetime.now().strftime('%Y_%m_%d__%H_%M')+".csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["cluster", "log_id", "Timestamp"])
            writer.writerows(log_list)


    def Get_Rank_Posistion(self, cardOfS, Lines_that_match_S, one_m):
        try:
            distance = 1.0 * cardOfS / Lines_that_match_S
        except ZeroDivisionError as er1:
            print(er1)
            print("cardOfS: " + str(cardOfS) + '\t' + 'Lines_that_match_S: ' + str(Lines_that_match_S))

        if distance <= self.para.lowerBound:
            if one_m:
                split_rank = 2
            else:
                split_rank = 1
        elif distance >= self.para.upperBound:
            if one_m:
                split_rank = 1
            else:
                split_rank = 2
        else:
            if one_m:
                split_rank = 1
            else:
                split_rank = 2

        return split_rank

    def DetermineP1P2(self, partition):
        if partition.lenOfLogs > 2:
            count_1 = 0

            uniqueTokensCountLS = []
            for columnIdx in range(partition.lenOfLogs):
                uniqueTokensCountLS.append(set())

            for logL in partition.logLL:
                for columnIdx in range(partition.lenOfLogs):
                    uniqueTokensCountLS[columnIdx].add(logL[columnIdx])

            # Count how many columns have only one unique term
            for columnIdx in range(partition.lenOfLogs):
                if len(uniqueTokensCountLS[columnIdx]) == 1:
                    count_1 += 1

            # Debug
            # strDebug = ''
            # for columnIdx in range(partition.lenOfLogs):
            # 	strDebug += str(len(uniqueTokensCountLS[columnIdx])) + ' '
            # print (strDebug)

            # If the columns with unique term more than a threshold, we return (-1, -1) to skip step 3
            GC = 1.0 * count_1 / partition.lenOfLogs

            if GC < self.para.CT:
                return self.Get_Mapping_Position(partition, uniqueTokensCountLS)
            else:
                return (-1, -1)


        elif partition.lenOfLogs == 2:
            return (0, 1)
        else:
            return (-1, -1)

    def Get_Mapping_Position(self, partition, uniqueTokensCountLS):
        p1 = p2 = -1

        # Caculate #unqiueterms in each column, and record how many column with each #uniqueterms
        numOfUniqueTokensD = {}
        for columnIdx in range(partition.lenOfLogs):
            if len(uniqueTokensCountLS[columnIdx]) not in numOfUniqueTokensD:
                numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] = 0
            numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] += 1

        if partition.stepNo == 2:

            # Find the largest card and second largest card
            maxIdx = secondMaxIdx = -1
            maxCount = secondMaxCount = 0
            for key in numOfUniqueTokensD:
                if numOfUniqueTokensD[key] > maxCount:
                    secondMaxIdx = maxIdx
                    secondMaxCount = maxCount
                    maxIdx = key
                    maxCount = numOfUniqueTokensD[key]
                elif numOfUniqueTokensD[key] > secondMaxCount and numOfUniqueTokensD[key] != maxCount:
                    secondMaxIdx = key
                    secondMaxCount = numOfUniqueTokensD[key]

            # Debug
            # print ("largestIdx: " + str(maxIdx) + '\t' + "secondIdx: " + str(secondMaxIdx) + '\t')
            # print ("largest: " + str(maxCount) + '\t' + "second: " + str(secondMaxCount) + '\t')

            # If the frequency of the freq_card>1 then
            if maxIdx > 1:
                for columnIdx in range(partition.lenOfLogs):
                    if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == maxCount:
                        # if len( uniqueTokensCountLS[columnIdx] ) == maxIdx:
                        if p1 == -1:
                            p1 = columnIdx
                        else:
                            p2 = columnIdx
                            break

                for columnIdx in range(partition.lenOfLogs):
                    if p2 != -1:
                        break
                    if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == secondMaxCount:
                        # if len( uniqueTokensCountLS[columnIdx] ) == secondMaxIdx:
                        p2 = columnIdx
                        break

            # If the frequency of the freq_card==1 then
            else:
                for columnIdx in range(len(uniqueTokensCountLS)):
                    if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == maxCount:
                        # if len( uniqueTokensCountLS[columnIdx] ) == maxIdx:
                        p1 = columnIdx
                        break

                for columnIdx in range(len(uniqueTokensCountLS)):
                    if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == secondMaxCount:
                        # if len( uniqueTokensCountLS[columnIdx] ) == secondMaxIdx:
                        p2 = columnIdx
                        break

            if p1 == -1 or p2 == -1:
                return (-1, -1)
            else:
                return (p1, p2)

        # If it is from step 1
        else:
            minIdx = secondMinIdx = -1
            minCount = secondMinCount = sys.maxsize
            for key in numOfUniqueTokensD:
                if numOfUniqueTokensD[key] < minCount:
                    secondMinIdx = minIdx
                    secondMinCount = minCount
                    minIdx = key
                    minCount = numOfUniqueTokensD[key]
                elif numOfUniqueTokensD[key] < secondMinCount and numOfUniqueTokensD[key] != minCount:
                    secondMinIdx = key
                    secondMinCount = numOfUniqueTokensD[key]

            # Debug
            # print ("smallestIdx: " + str(minIdx) + '\t' + "secondIdx: " + str(secondMinIdx) + '\t')
            # print ("smallest: " + str(minCount) + '\t' + "second: " + str(secondMinCount) + '\t')

            for columnIdx in range(len(uniqueTokensCountLS)):
                if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == minCount:
                    # if len( uniqueTokensCountLS[columnIdx] ) == minIdx:
                    if p1 == -1:
                        p1 = columnIdx
                        break

            for columnIdx in range(len(uniqueTokensCountLS)):
                if numOfUniqueTokensD[len(uniqueTokensCountLS[columnIdx])] == secondMinCount:
                    # if len( uniqueTokensCountLS[columnIdx] ) == secondMinIdx:
                    p2 = columnIdx
                    break

            return (p1, p2)

    def PrintPartitions(self):
        for idx in range(len(self.partitionsL)):
            print('Partition {}:(from step {})    Valid:{}'.format(idx, self.partitionsL[idx].stepNo,
                                                                   self.partitionsL[idx].valid))

            for log in self.partitionsL[idx].logLL:
                print(log)

            print("*****************************************")

    def PrintEventStats(self):
        for event in self.eventsL:
            if event.eventCount > 1:
                print(str(event.eventId) + '\t' + str(event.eventCount))
                print(event.eventStr)

    def deleteAllFiles(self, dirPath):
        fileList = os.listdir(dirPath)
        for fileName in fileList:
            os.remove(dirPath + "/" + fileName)

def splitIPLoM(params, report, toSplit):
    print(report["report"])
    print(toSplit)
    report_idx = (idx for idx,item in enumerate(report["report"]) if item["eventId"] == toSplit).__next__()
    fixed_tag_idx = [idx for idx, tag in enumerate(report["report"][report_idx]["tags"]) if tag["tag"] != "*"]
    para = Para(path=report["full_path"], removable=True,
                removeCol=fixed_tag_idx,
                maxEventLen=params["maxEventLen"],
                step2Support=params["step2Support"],
                PST=params["use_pst"],
                CT=params["CT"],
                lowerBound=params["lowerBound"],
                upperBound=params["upperBound"],
                usePST=params["use_pst"],
                get_stars=True
                )

    myparser = IPLoM(para)
    res = myparser.splitProcess(report, toSplit)

    print('The running time of IPLoM is', res['time'])
    return res



def runIPLoM(params):
    print(params)
    removable = True if params["remove_col"] else False
    regular = True if params["remove_expression"] else False

    para = Para(path=params["path"], logname=params["log_id"], savePath=params["savePath"], removable=removable,
                removeCol=params["remove_col"], regular=regular, rex=params["remove_expression"],
                line_starter=params["line_starter"], remove_chars=params["remove_chars"],
                first_line=params["first_line"], last_line=params["last_line"],
                transform_chars=params["transform_chars"],maxEventLen=params["maxEventLen"],
                step2Support=params["step2Support"],PST=params["use_pst"],CT=params["CT"],
                lowerBound=params["lowerBound"],upperBound=params["upperBound"],usePST=params["use_pst"],
                get_stars=True, saveFileName = params["saveFileName"]+"/"
                )

    myparser = IPLoM(para)
    res = myparser.mainProcess()

    print('The running time of IPLoM is', res['time'])
    return res


# A simple example to run the code independently from the app
if __name__== '__main__':
    # Some parameters to run the rdm-error log file
    params = {'first_line': 0, 'remove_col': None, 'transform_chars': [('\(', ' ( '), ('\)', ' ) '), ('=', '= '), (',', ' , '), ('sql-thread-', 'sql-thread- ')], 'last_line': -1, 'line_starter': '(([0-9]+)-([0-9]+)-([0-9]+) ([0-9]+):([0-9]+):([0-9]+).([0-9]+))', 'remove_expression': ['(([0-9]+)-([0-9]+)-([0-9]+) ([0-9]+):([0-9]+):([0-9]+).([0-9]+))'], 'remove_chars': [';', ':', '-', '\|', '\[', '\]'], 'path': '/home/hamza/Desktop/projet_s5/project files/data_in/rdm-error.log', 'step2Support': 0.0, 'use_pst': 0.0, 'lowerBound': 0.35, 'maxEventLen': 150, 'upperBound': 0.9, 'CT': 0.0, 'savePath': './reports/', 'log_id': '3'}
    removable = True if params["remove_col"] else False
    regular = True if params["remove_expression"] else False

    para = Para(path=params["path"], logname=params["log_id"], savePath=params["savePath"], removable=removable,
                removeCol=params["remove_col"], regular=regular, rex=params["remove_expression"],
                line_starter=params["line_starter"], remove_chars=params["remove_chars"],
                first_line=params["first_line"], last_line=params["last_line"],
                transform_chars=params["transform_chars"], maxEventLen=params["maxEventLen"],
                step2Support=params["step2Support"], PST=params["use_pst"], CT=params["CT"],
                lowerBound=params["lowerBound"], upperBound=params["upperBound"], usePST=params["use_pst"],
                get_stars=True, saveFileName = params["log_id"]+"/"
                )

    myparser = IPLoM(para)
    res = myparser.mainProcess()

    print('The running time of IPLoM is', res['time'])
