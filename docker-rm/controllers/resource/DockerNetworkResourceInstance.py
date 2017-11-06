import logging
from controllers.resource.ResourceInstance import *
from controllers.util.Config import *
import docker

class DockerNetworkResourceInstance(ResourceInstance):
	""" Reponsible for running docker-network resource instance lifecycles"""
	
	def __init__(self,networkType,name,location='',properties={},network=None):
		self.logger = logging.getLogger(__name__)
		self.logger.debug('creating new docker network resource instance '+name)

		self.network=network

		if network!=None:
			self.logger.debug('creating proxy for existing network')
			self.logger.debug(network.attrs)

			# call parent with type and default properties
			super().__init__(networkType, network.name,globalConfig.locationDescriptor['locations'][0]['name'],properties)

			# means this network is managed outside RM
			self.readonly=True

			self.properties={
				'networkname': network.name,
				'subnet':'',
				'gateway':'',
				'networkid':network.attrs['Id']
			}

			config=network.attrs['IPAM']['Config']
			if len(config) > 0:
				self.logger.debug("found network config for network "+network.name+' '+str(network.attrs['IPAM']['Config'][0]))
				if 'Subnet' in network.attrs['IPAM']['Config'][0] :
					self.properties['subnet']=network.attrs['IPAM']['Config'][0]['Subnet']
				if 'Gateway' in network.attrs['IPAM']['Config'][0] :
					self.properties['gateway']=network.attrs['IPAM']['Config'][0]['Gateway']
			else:
				self.logger.debug('no network config found for network '+network.name)

			self.logger.debug(self.properties)
		else:
			self.logger.debug('creating new network')

			# means this network can be deleted by RM
			self.readonly=False

			# call parent with type and default properties
			super().__init__(networkType, name,globalConfig.locationDescriptor['locations'][0]['name'],properties)


	def createNetwork(self):
		self.logger.debug('creating network '+self.name+' with properties '+str(self.properties))

		ipam_pool = docker.types.IPAMPool(
			subnet=self.properties['subnet'],
			gateway=self.properties['gateway']
		)
		ipam_config = docker.types.IPAMConfig(
			pool_configs=[ipam_pool]
		)
		
		self.properties['bridgename']="net"+str(self.resourceId)		
		dockerOptions={
			"com.docker.network.bridge.name":self.properties['bridgename']
		}

		self.logger.debug('about to call create network')
		self.logger.debug(controllers.resource.ResourceInstance.dockerClient)
		self.network=controllers.resource.ResourceInstance.dockerClient.networks.create(self.properties['networkname'],
																					driver="bridge",
																					options=dockerOptions,
																					ipam=ipam_config)
		self.logger.debug('created network '+str(self.network))
		
		self.properties['networkid']=self.network.id
		self.logger.debug(self.network.attrs)


	def getID(self):
		self.logger.debug('getting network instance id')
		return self.network.id

	def removeNetwork(self):
		self.logger.debug('destroying network '+self.network.name)
		self.network.remove()
			
	# replace standard transition with create network instead of create container
	def runStandardTransition(self, transitionName, properties):
		self.logger.debug('running standard transition for docker network')

		if transitionName=='uninstall':
			if self.readonly==False:
				self.logger.debug('killing docker-network')
				try:
					self.removeNetwork()

					#remove resource instance from the list
					removeResourceInstance(self.resourceId)

					ret={'status':'OK'}
				except docker.errors.APIError:
					ret={'status':'Failed'}
				return ret
			else:
				self.logger.debug('cannot delete read only docker networks')
				# return OK for the case where we are proxying pre-existing networks
				return {'status':'OK'}

		if transitionName=='install':
			self.logger.debug('creating network for install transition')
			self.createNetwork()
			return {'status':'OK'}


	# no operations on a network
	def runOperation(self, transitionName,properties):
		self.logger.error('should not try to run operations on a docker-network')

