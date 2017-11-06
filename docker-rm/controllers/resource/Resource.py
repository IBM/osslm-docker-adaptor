import logging
from pathlib import Path
import os
from datetime import datetime
import pytz
import yaml

class Resource:
	# Reponsible for loading and managing resource types from the filesystem
	
	def __init__(self,path,internal=False):
		# for each resource

		self.logger = logging.getLogger(__name__)
		self.logger.debug('Creating new resource type '+str(path))

		# collect basic resource parameters
		self.path=path
		self.createdAt=str(datetime.fromtimestamp(os.path.getmtime(str(path)),pytz.UTC).astimezone().isoformat())
		self.name='resource::'+path.name+'::1.0'
		self.imageName="dockerrm_"+path.name

		# boolean for internal or external resource
		self.internal=internal

		# if this is not internal then read the lifecycle and operational 		
		if internal==False:
			self.lifecyclePath=self.loadLifecycleConfig()
			self.operationsPath=self.loadOperationsConfig()
		else:
			self.lifecyclePath=None
			self.operationsPath=None

		# load resource descriptor from filesystem		
		self.resourceDescriptorString=''
		self.resourceDescriptor=self.loadResourceDescriptor()

#		self.logger.info('created resource '+self.name +' ' + self.resourceDescriptorString)
		
	def loadResourceDescriptor(self):
		# 
		resfilename = str(self.path)+'/resource.yaml'
		self.logger.debug('looking for resource descriptor '+resfilename)

		resourceDescriptorFile = Path(resfilename)
		if resourceDescriptorFile.is_file():
			self.logger.debug('found '+resfilename)
		    # file exists
			with open(resfilename, 'rt') as f:
				self.resourceDescriptorString=f.read()
				self.logger.debug('read descriptor '+self.resourceDescriptorString)
				return yaml.safe_load(self.resourceDescriptorString)
		else:
			self.logger.debug('no resource descriptor file '+resfilename+' found')
			return None

	def loadLifecycleConfig(self):
		filename=str(self.path)+'/lifecycle/lifecycle.yaml'
		self.logger.debug('looking to see if lifecycle yaml file '+filename+' is available')

		lifecycleFile = Path(filename)
		if lifecycleFile.is_file():
			self.logger.debug('found '+filename)
			with open(filename, 'rt') as f:
				return yaml.safe_load(f.read())
		else:
			self.logger.debug('no lifecycle config file '+filename+' found')
			return None

	def loadOperationsConfig(self):
		filename=str(self.path)+'/operations/operations.yaml'
		self.logger.debug('looking to see if operations yaml file '+filename+' is available')

		operationsFile = Path(filename)
		if operationsFile.is_file():
			self.logger.debug('found '+filename)
			with open(filename, 'rt') as f:
				return yaml.safe_load(f.read())
		else:
			self.logger.debug('no operations config file '+filename+' found')
			return None

	def isStandardTransition(self, transitionName):
		self.logger.debug('check if '+transitionName+' is a supported standard transition')
		self.logger.debug(self.resourceDescriptor['lifecycle'])

		transitionList= [element.lower() for element in self.resourceDescriptor['lifecycle']]
		if transitionName.lower() in transitionList:
			self.logger.debug('found transition in resource descriptor')
			return True

		return False

	def isOperation(self, transitionName):
		self.logger.debug('check if '+transitionName+' is supported operation')
		if transitionName == 'addNetwork' or transitionName == 'removeNetwork':
			self.logger.debug('standard network operation '+transitionName)
			return True
		
		self.logger.debug(self.resourceDescriptor['operations'])

		if transitionName in self.resourceDescriptor['operations']:
			self.logger.debug('found '+transitionName+' in operations')
			return True
		
		return False		

	def getResourceOverview(self):
		self.logger.debug('get resource overview')
		resp={
			'createdAt':self.createdAt,
			'lastModifiedAt':self.createdAt,
			'name':self.name,
			'state':'PUBLISHED'
		}
		self.logger.debug(resp)
		return resp

	def getResourceDetails(self):
		self.logger.debug('get resource overview')
		resp={
			'createdAt':self.createdAt,
			'lastModifiedAt':self.createdAt,
			'descriptor':self.resourceDescriptorString,
			'name':self.name,
			'state':'PUBLISHED'
		}
		self.logger.debug(resp)
		return resp