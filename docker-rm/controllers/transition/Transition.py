import logging
import threading
from datetime import datetime, timezone
from controllers.util.DB import *
from controllers.transition.TransitionTasks import *
from controllers.transition.InstallTransitionTask import InstallTransitionTask
from controllers.transition.ConfigureTransitionTask import ConfigureTransitionTask
from controllers.transition.StartTransitionTask import StartTransitionTask
from controllers.transition.IntegrityTransitionTask import IntegrityTransitionTask
from controllers.transition.StopTransitionTask import StopTransitionTask
from controllers.transition.UninstallTransitionTask import UninstallTransitionTask
from controllers.transition.OperationTransitionTask import OperationTransitionTask
from controllers.resource.ResourceInstance import *
from controllers.util.Kafka import *
from controllers.util.Config import *
from controllers.ResourceManager import *
from controllers.resource.Resource import Resource

# placeholder for generating transition ids
transitionId=0

class Transition:
	""" 
		Transition object
	    -----------------
	    Manages a unique transition request, and all asynchronus running tasks 
	    that are executing it.
	"""
	def __init__(self, transitionRequest=None):
		self.logger = logging.getLogger(__name__)
		self.logger.debug('creating a new transition')
		self.logger.debug(transitionRequest)

		self.startedAt=str(datetime.now(timezone.utc).astimezone().isoformat())
		self.requestState='IN_PROGRESS'		
		self.requestStateReason=''
		self.finishedAt=''
		self.requestId=0
		self.properties=None
		self.resourceName=None
		self.metricKey=None
		self.resourceId=None
		self.resourceTypeName=None
		self.resourceManagerId=None
		self.deploymentLocation=None
		self.transitionName=None
		
		if transitionRequest!=None:
			if 'properties' in transitionRequest:
				self.properties=transitionRequest['properties']
			if 'transitionName' in transitionRequest:
				self.transitionName=transitionRequest['transitionName']
			if 'resourceManagerId' in transitionRequest:
				self.resourceManagerId=transitionRequest['resourceManagerId']
			if 'deploymentLocation' in transitionRequest:
				self.deploymentLocation=transitionRequest['deploymentLocation']
			if 'resourceName' in transitionRequest:
				self.resourceName=transitionRequest['resourceName']
			if 'metricKey' in transitionRequest:
				self.metricKey=transitionRequest['metricKey']
			if 'resourceId' in transitionRequest:
				self.resourceId=transitionRequest['resourceId']
			if 'resourceType' in transitionRequest:
				self.resourceTypeName=transitionRequest['resourceType']

			# assign a new transitionId to new request
			global transitionId
			transitionId=transitionId+1
			self.requestId=transitionId
			#save to db
			self.eid=dbClient.createNewTransitionRequest(self.getTransitionRequestStatus())

		self.task=None
		self.resourceInstance=None
		try:
			self.parseTransitionRequest()
		except Exception as ex:
			self.delete()
			raise ex
			
			
				
	def parseTransitionRequest(self):
		self.logger.debug('parsing transition request for transition='+str(self.transitionName)+' on resource='+str(self.resourceId))
		# figure out if an operation or a transition, find or create a resource instance
		# and create appropriate task
        
		if self.transitionName==None:
			self.logger.error('must have a transition')
			raise controllers.ResourceManager.InvalidTransitionException(self)
		
		if self.resourceId != None:
			
			self.logger.debug('get resource with id '+self.resourceId)
			# get the resource instance
			instance=controllers.ResourceManager.resourceManager.findInstanceById(self.resourceId)
			if instance == None:
				self.logger.error('cannot find resource instance with id '+self.resourceId)
				raise InstanceNotFoundException(self.resourceId)

			# check the transition against standard lifecycles, then check against operations

			std=['Install','Configure','Start','Integrity','Stop','Uninstall']
			if self.transitionName in std:

				if instance.type.isStandardTransition(self.transitionName):
					# if standard transition then call standard transition
					self.logger.debug('standard transition '+self.transitionName+' requested')

					if self.transitionName.lower()=='configure':
						self.task=ConfigureTransitionTask(self,instance)
					elif self.transitionName.lower()=='start':
						self.task=StartTransitionTask(self,instance)
					elif self.transitionName.lower()=='stop':
						self.task=StopTransitionTask(self,instance)
					elif self.transitionName.lower()=='uninstall':
						self.task=UninstallTransitionTask(self,instance)
					elif self.transitionName.lower()=='integrity':
						self.task=IntegrityTransitionTask(self,instance)
					elif self.transitionName.lower()=='install':
						message = 'Install requested on an existing resource with id: '+ str(self.resourceId)
						self.logger.error(message)
						raise controllers.ResourceManager.InvalidTransitionException(message)
					else:	
						self.logger.debug('A standard transition should have been processed, ' + self.transitionName + ' is not recognised')
						raise controllers.ResourceManager.InvalidTransitionException(self.transitionName)
				else:
					self.logger.debug('this is not an implemented standard transition')
					raise controllers.ResourceManager.InvalidTransitionException(self.transitionName)

			elif instance.type.isOperation(self.transitionName):
				# else if not then call operations transition
				self.logger.debug('operation '+self.transitionName+' requested')
				self.task=OperationTransitionTask(self,instance)

			else:
				self.logger.error('cannot run transition '+self.transitionName+' on existing instance id')
				raise controllers.ResourceManager.InvalidTransitionException(self.transitionName)

		else:
			# if there is no resource id, then create a new resource Install task
			self.logger.debug ('no id found - creating new instance task')

			resourceType=controllers.ResourceManager.resourceManager.getResourceType(self.resourceTypeName)
			if resourceType==None:
				raise controllers.ResourceManager.TypeNotFoundException(self.resourceTypeName)
			if resourceType.isStandardTransition(self.transitionName)==False:
				raise controllers.ResourceManager.InvalidTransitionException(self.transitionName)

			# task to run is install
			self.task=InstallTransitionTask(self)

	def loadFromDB(self, requestId):
		self.logger.debug('loading transition from DB with request id '+requestId)

		dbRequest=dbClient.findTransitionByRequestID(requestId)
		if dbRequest==None:
			self.logger.error('cannot find transition with request id='+requestId)
			raise NoTransitionFoundException(requestId)
		else:
			self.requestId-dbRequest.requestId
			self.transitionName=dbRequest.transitionName
			self.startedAt=dbRequest.startedAt
			self.properties=dbRequest.properties
			self.deploymentLocation=dbRequest.deploymentLocation
			self.resourceName=dbRequest.resourceName
			self.finishedAt=dbRequest.finishedAt
			self.requestState=dbRequest.requestState
			self.requestStateReason=dbRequest.requestStateReason
			self.eid-dbRequest.eid

	def updateDB(self):
		self.logger.debug('updating transition in database')
		dbClient.updateTransitionRequest(self.eid, self.getTransitionRequestStatus())

	def delete(self):
		self.logger.debug('deleting transition with request id '+str(self.requestId))
		dbClient.removeTransition(self.eid)

	def getTransitionRequestStatus(self):
		self.logger.debug('get transition request called')
		self.logger.debug(globalConfig)
		context={
			'AsynchronousTransitionResponses':globalConfig.configDescriptor['supportedFeatures']['asynchronousTransitionResponse']
			}

		return {'requestId': self.requestId,
				'finishedAt':self.finishedAt,
				'requestId':self.requestId,
				'requestState':self.requestState,
				'requestStateReason': self.requestStateReason,
				'resourceId': str(self.resourceId),
				'startedAt':self.startedAt,
				'context':context,
				'transitionName':self.transitionName
				}

	def getTransitionRequestResponse(self):
		self.logger.debug('get transition request called')
		context={
			'AsynchronousTransitionResponses':globalConfig.configDescriptor['supportedFeatures']['asynchronousTransitionResponse']
			}

		return {'requestId': self.requestId,
				'requestState':self.requestState,
				'context':context
				}

	def runTransition(self):
		""" 
		Spawn a thread that runs a transition, return response and when thread completes
		  - update status of thread in DB
		  - send notification on Kafka if it is configured
		"""
		self.logger.debug('running run Transition')

		if self.task !=None:
			self.logger.debug('running transition '+self.transitionName+' on resource instance '+str(self.task.resourceInstance.resourceId))
			self.task.start()
		else:
			raise Exception()

		self.finishedAt=str(datetime.now(timezone.utc).astimezone().isoformat())

		return self.getTransitionRequestResponse()
