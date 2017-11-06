import logging
import threading
from datetime import datetime, timezone
#from controllers.util.DB import *
from controllers.resource.ResourceInstance import *
from controllers.util.Kafka import *
from controllers.transition.Transition import *

lock = threading.Lock()

class TransitionTask(threading.Thread):

	def __init__(self, transition, resourceInstance=None):

		threading.Thread.__init__(self)
		self.logger = logging.getLogger(__name__)
		self.logger.info('new transition task thread with transition '+str(transition.transitionName)+' and instance '+str(resourceInstance))
		self.transition=transition
		self.resourceInstance=resourceInstance
		self.logger.debug('finished init of transition task')

	def validateOperationProperties(self, operationName, resourceType):
		self.logger.debug('validating operation '+operationName+' properties')
		if operationName=='addNetwork' or operationName=='removeNetwork':
			self.logger.debug('found standard network operations')
			return self.validateProps({
				'networkid':{
				    'type': 'string'
				}
			})
		
		if resourceType!=None:
			self.logger.debug('resource properties are '+str(resourceType.resourceDescriptor['properties']))
			#loop over type properties and make sure all are in transition if not defaulted
			return self.validateProps(resourceType.resourceDescriptor['operations'][operationName]['properties'])

	def validateStandardProperties(self, resourceType):
		# validate all properties are present, returns boolean
		self.logger.debug('validating properties on transition '+str(self.transition.properties))
		if resourceType!=None:
			self.logger.debug('resource properties are '+str(resourceType.resourceDescriptor['properties']))
			#loop over type properties and make sure all are in transition if not defaulted
			resp=self.validateProps(resourceType.resourceDescriptor['properties'])
			return resp

	def validateProps(self,props):
		self.logger.debug('validating properties')
		# guard against no properties section at all, there may still be optional properties in descriptor
		transitionProperties = {}		
		if  hasattr(self.transition, 'properties'):
			transitionProperties = self.transition.properties
					
		if transitionProperties==None:
			transitionProperties = {}
			
		self.logger.debug('Properties to validate against descriptor: ' +str(transitionProperties))
		
		if props==None:
			self.logger.error('no properties found')
			return False;

		for p in props:
			self.logger.debug('expecting '+str(props))
			if 'default' in props[p]:
				self.logger.debug('default value provided so pass')
				pass
			elif 'value' in props[p]:
				self.logger.debug('value provided so pass')
				pass
			elif 'read-only' in props[p] and props[p]['read-only']==True:
				self.logger.debug('read only value so pass')
				pass
			elif p in transitionProperties:
				self.logger.debug('found it')
			elif 'required' not in props[p]:
				self.logger.debug('property is missing but not required so pass')
				pass
			elif 'required' in props[p] and props[p]['required']==False:
				self.logger.debug('property is missing but not required = False so pass')
				pass
			else:
				self.logger.error('missing property '+p)
				raise controllers.transition.TransitionTasks.MissingPropertiesException(p)
				
		return True

	def checkExistingNetwork(self):
		self.logger.debug("checking if this is a network type, if it exists and if it is read only")
		
		if self.resourceInstance.type.name=="resource::docker-network::1.0" and self.resourceInstance.readonly==True:
			self.logger.debug('existing read only network found')
			return True
		
		self.logger.debug('not existing readonly network')
		return False

	def reportFailedTask(self, reason):
		self.logger.debug('Failed task - updating DB with failure and error')
		self.transition.requestState='FAILED'
		self.transition.requestStateReason=reason
		self.transition.finishedAt=str(datetime.now(timezone.utc).astimezone().isoformat())
		
		
	def run(self, transitionName, standardLifecycle=True):
		self.logger.debug('run transition '+ transitionName 
						+ ' resource id: ' + str(self.transition.resourceId) 
						+ ' request id: ' + str(self.transition.requestId))
		resp=None
		
		# if this is a read only network then just return true
		if self.checkExistingNetwork():
			self.logger.debug('mark install complete for pre-existing network')
			self.transition.requestState='COMPLETED'
			self.transition.finishedAt=str(datetime.now(timezone.utc).astimezone().isoformat())
		else:
			try:
				if standardLifecycle==True:
					self.logger.debug('running standard transition '+transitionName)
					resp=self.resourceInstance.runStandardTransition(transitionName,self.transition.properties)
				else:
					self.logger.debug('running operation '+transitionName)
					resp=self.resourceInstance.runOperation(transitionName,self.transition.properties)
				self.logger.debug('marking transition COMPLETED')	
				self.transition.requestState='COMPLETED'
				self.transition.finishedAt=str(datetime.now(timezone.utc).astimezone().isoformat())
			except Exception as ex:
				self.logger.error('caught transition exception '+ str(type(ex).__name__) + ' ' +str(ex))
				
				resp=None
				self.reportFailedTask("Failure from Virtual Infrastructure: " + str(ex))
	
			self.logger.debug(resp)
			
	
		if self.transition.resourceId==None:
			self.logger.debug('adding resource id to transition object')
			self.transition.resourceId=self.resourceInstance.resourceId

		# update the transition in database
		self.logger.debug('updating transition status in database')
		with lock:
			self.transition.updateDB()

		# send update to kafka
		self.logger.info('completed task '+str(self.transition.requestId)+' with response ='+str(self.transition.getTransitionRequestStatus()))
		kafkaClient.sendLifecycleEvent(self.transition.getTransitionRequestStatus())

		# send additional info to kafka for reporting		
		extraEventInfo={
			'resourceId':self.resourceInstance.resourceId,
			'lastTransitionName':self.transition.transitionName,
			'name':self.resourceInstance.name,
			'typename':self.resourceInstance.type.name,
			'properties':self.resourceInstance.properties,
		}
		
		# add container information if this is not a network
		if self.resourceInstance.type.name != "resource::docker-network::1.0":
			# if the  container didn't get created, then there won't be an id or conatiner
			if self.resourceInstance.getID() != None:
				extraEventInfo['dockerInstance']={
					'id':self.resourceInstance.getID(),
					'attrs':self.resourceInstance.container.attrs
				}
		
		kafkaClient.sendLifecycleEvent(extraEventInfo)


class NoTransitionFoundException(Exception):
	def __init__(self, requestId):
		self.requestId=requestId

class MissingPropertiesException(Exception):
	def __init__(self, missingProperty):
		self.missingProperty = missingProperty