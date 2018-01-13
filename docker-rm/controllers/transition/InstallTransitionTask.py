import logging
from controllers.transition.TransitionTasks import TransitionTask
from controllers.transition.TransitionTasks import MissingPropertiesException
from controllers.util.Config import *
import controllers.ResourceManager

class InstallTransitionTask(TransitionTask):
	# create a task to install a new resource 
	def __init__(self, transition):
		# validate transition has required values and properties
		self.logger = logging.getLogger(__name__)
		self.logger.debug('creating new install transition task for transition '+str(transition))

		super().__init__(transition)

		self.logger.debug('location='+transition.deploymentLocation)

		if self.transition.deploymentLocation == None:
			self.logger.debug('no deployment location found in transition request')
			raise controllers.ResourceManager.NoLocationInRequestException()
		else:
			self.logger.debug('searching for location'+self.transition.deploymentLocation+' in location descriptor')
			self.logger.debug(globalConfig.locationDescriptor['locations'])

			if not any(loc['name']==self.transition.deploymentLocation for loc in globalConfig.locationDescriptor['locations']):
				self.logger.debug('location not found in config')
				raise controllers.ResourceManager.UnknownLocationInRequestException(transition.deploymentLocation)

		if self.transition.transitionName.lower()!='install':
			self.logger.error('cannot run transition '+self.transition.transitionName+' without valid instance id')
			""" throw an exception here """
			raise controllers.ResourceManager.InvalidTransitionException(self.transition.transitionName)

		if self.transition.resourceTypeName==None:
			raise controllers.ResourceManager.TypeMissingFromRequestException()

		resourceType=controllers.ResourceManager.resourceManager.getResourceType(self.transition.resourceTypeName)
		if resourceType==None:
			raise controllers.ResourceManager.TypeNotFoundException(self.transition.resourceTypeName)
		
		super().validateStandardProperties(resourceType)
		# validate input properties and raise an exception if False is returned
		#if super().validateStandardProperties(resourceType) ==False:
		#	self.logger.error('missing properties')
		#	raise MissingPropertiesException()
		
		# metric key is passed in all install requests
		self.transition.properties['metricKey'] = transition.metricKey
		
		self.resourceInstance=controllers.ResourceManager.resourceManager.createNewResourceInstance(
				resourceType,
				self.transition.resourceName, 
				self.transition.deploymentLocation, 
				self.transition.properties
				)
		self.resourceId=self.resourceInstance.resourceId
		
		self.logger.debug('instance to be run='+str(self.resourceInstance.resourceId))

	def run(self):
		self.logger.debug('running install transition')

		super().run('install')

	def validateProperties(self):
		self.logger.debug('validating install properties are there')

