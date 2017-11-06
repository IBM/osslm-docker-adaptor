import logging
import csv
import os
from controllers.util.Config import *
from datetime import datetime, timezone
import pytz

# the file to output trace messages to
traceFile=None
traceWriter=None
logger = logging.getLogger(__name__)

def setupTrace():
    # look in config and see if trace is set
    logger.debug('setting up trace file if required')
    if globalConfig.configDescriptor['properties']['generateTraceFile']:
        # create trace file
        logger.debug('tracing is enabled')
        global traceFile
        global traceWriter
        traceFile = open(globalConfig.configDescriptor['properties']['traceFile'],'w')
        #traceWriter = csv.writer(traceFile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_NONNUMERIC)
        traceWriter = csv.writer(traceFile,quoting=csv.QUOTE_NONNUMERIC)
        traceWriter.writerow(["time","api called","input message", "response"])

def traceMessage(name,input,response):
    logger.debug('tracing message to trace file '+str(name)+' '+str(input)+' '+str(response))
    # output a request payload and newline
    global traceWriter
    if traceWriter!=None:
        logger.debug('tracing active')
        time=datetime.now(timezone.utc).astimezone().isoformat()
        traceWriter.writerow([str(time),name,str(input),str(response)])
        traceFile.flush()
    
def closeTrace():
    logger.debug('close the trace file')
    if traceFile!=None:
        traceFile.close()