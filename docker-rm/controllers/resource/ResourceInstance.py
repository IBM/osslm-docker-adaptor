import docker
import logging
from datetime import datetime, timezone
from controllers.resource.Resource import Resource
import controllers.ResourceManager
import sys
from controllers.util.Config import *
import yaml


##########################################################################################
# docker connection
##########################################################################################
dockerClient=None
logger=logging.getLogger(__name__)
try:
	dockerClient = docker.from_env()
	dockerClient.ping()
	logger.debug('docker client configured and successfully pinged server')
except Exception as e:
	logger.error(type(e).__name__)
	logger.error(str(e))
	logger.error('Docker environment variables must be provided, please re-run with correct Docker environment')
	sys.exit(0)

##########################################################################################
# resource instances and managements
##########################################################################################

# id of last allocated resource instance
lastResourceId=0

# list of all resource instances
resourceInstances=[]

def findInstanceByResourceId(id):
	logger.debug('searching for instance with resource id '+str(id))

	for i in resourceInstances:
		if i.resourceId==int(id):			
			return i
	logger.debug('could not find instance ')
	return None

def findInstances(location, typename):
	logger.debug('searching for instances in '+location)

	# partial and full search of all instances with a particular name
	instances=[]
	for i in resourceInstances:
		if location!=None and i.location==location:
			if typename !=None:
				if i.type.name==typename:
					instances.append(i.getInstanceDetails())
			else:
	 			instances.append(i.getInstanceDetails())

	return instances

def findInstancesByLocation(location, name, typename):
	logger.debug('find instance in location: '+location+' with name: '+name+' with type: '+typename)
	# partial and full search of all instances with a particular name in a provided location
	# return single instance exact match
	for i in resourceInstances:
		if location!=None and i.location==location:
			if typename !=None and i.type.name==typename:
				if name!=None and i.name==name:
					return i
	logger.debug('found no network')
	return None

def removeResourceInstance(id):
	# expecting an integer id
	logger.debug('removing resource instance '+str(id))
	index=0;
	for p in resourceInstances:
		if p.resourceId==id:
			logger.debug('found it')
			del resourceInstances[index]
			logger.debug('deleted '+str(id))
		index=index+1


##########################################################################################
# resource instance class
##########################################################################################
class ResourceInstance:
	""" Responsible for running resource instance lifecycles"""
	
	def __init__(self,resourceType=None,name='',location='',properties={}):
		self.logger = logging.getLogger(__name__)
		self.logger.info('creating new resource instance with name='+name)

		self.type=resourceType

		self.properties=self.createProperties()
		self.updateProperties(properties)

		self.location=location

		self.createdAt=str(datetime.now(timezone.utc).astimezone().isoformat())

		self.lastModifiedAt=str(datetime.now(timezone.utc).astimezone().isoformat())

		self.name=name

		global lastResourceId
		self.resourceId=lastResourceId
		lastResourceId=lastResourceId+1

		self.container=None

		self.readonly=False

		# add self to list of instances
		global resourceInstances
		resourceInstances.append(self)

	def createProperties(self):
		self.logger.debug('creating properties')
		props={}
		for p in self.type.resourceDescriptor['properties']:
			self.logger.debug('adding '+str(p))
			self.logger.debug(self.type.resourceDescriptor['properties'][p])
			if 'default' in self.type.resourceDescriptor['properties'][p]:
				props[p]=self.type.resourceDescriptor['properties'][p]['default']
			else:
				props[p]=''

		self.logger.debug(props)
		return props

	def updateProperties(self, properties):
		self.logger.debug('updating with passed in properties')
		self.logger.debug(properties)
		for p in properties:
			self.logger.debug(p)
			self.properties[str(p)]=properties[str(p)]

		self.logger.debug(self.properties)

	def startContainer(self):
		self.logger.debug('starting container')
		""" check if image exists, if not throw an exception """
		image=None
		try:
			image=dockerClient.images.get(self.type.imageName)

		except docker.errors.ImageNotFound as ex:
			self.logger.debug('no image found for '+self.type.name + ' called ' + self.type.imageName)
			removeResourceInstance(self.resourceId)
			raise

		# pass all properties as env variables here
		# create a list of env strings with all key, values
		self.logger.debug('PASS PROPERTIES AS ENV HERE')
		envlist=[]
		for key, value in self.properties.items():
			env='RM_PROP_'+str(key)+'='+str(value)
			envlist.append(env)
		self.logger.debug('environment variables='+str(envlist))

		network='bridge'
		hostname=self.name
		for key, value in self.properties.items():
			if key=='docker_network':
				self.logger.debug('FOUND docker network ...')
				network=value

			# check if there is a docker_hostname property, if so set the hostname
			elif key=='docker_hostname':
				self.logger.debug('docker hostname set to '+value)
				hostname=value

		self.logger.debug('startup network ='+network)
		self.logger.debug('hostname ='+hostname)

		""" run the docker container """
		
		self.logger.debug('creating docker container for '+self.type.name)
		volumeList=[]
		volumeList.append("/sys/fs/cgroup:/sys/fs/cgroup:ro")
		
		if 'openPublicPorts' in globalConfig.configDescriptor['properties']:
			public_ports_policy=globalConfig.configDescriptor['properties']['openPublicPorts']
			# eval string to boolean
			public_ports_policy=str(public_ports_policy) == "True"
		else:
			public_ports_policy=False
			
		self.logger.debug('public_ports_policy = '+str(public_ports_policy))
			
		try:
			self.container=dockerClient.containers.run(self.type.imageName,
													name=self.type.imageName+str(self.resourceId),
													environment=envlist,
													hostname=hostname,
													network=network,
													detach=True,
													privileged=True,
													publish_all_ports=public_ports_policy,
													volumes=volumeList)
		except (docker.errors.APIError, docker.errors.ContainerError) as ex:
			# Need to check if a container was created and remove it if it was.
			self.logger.error(str(ex))
			name = self.type.imageName+str(self.resourceId)
			containers = dockerClient.containers.list(all=True, filters={'name': name})
			if len(containers) == 1:
				self.logger.debug("Removing container that was created with error: " + name)
				containers[0].remove()			
			raise ex
		
		# wait for a second and check for ip address
		self.container.reload()
		self.logger.debug('attributes='+str(self.container.attrs))
		self.logger.debug('-------------------------------------')
		self.logger.debug(self.container.attrs['NetworkSettings']['Networks'][network])
		self.logger.debug('-------------------------------------')
		self.properties['docker_ipaddr']=self.container.attrs['NetworkSettings']['Networks'][network]['IPAddress']
		
		#if the network set was host network then no ip address will be allocated so pass something dummy back
		if network=='host':
			self.properties['docker_ipaddr']='HOSTIP'

		# public ports if any
		port_mappings=self.container.attrs['NetworkSettings']['Ports']; 	
		self.logger.debug('port_mappings: ' + str(port_mappings))
		if port_mappings is not None:
			for val in port_mappings:
				next_port_mapping=port_mappings[val]
				if next_port_mapping is not None:
					self.logger.debug(val + ' mapped to ' + str(next_port_mapping[0])) 
					self.properties['port_mapping_'+ val]=next_port_mapping[0]['HostPort']

		# if there are additional docker_network properties, then add those networks to the container 
		# and update the read-only propeties for each if they exist
		for key, value in self.properties.items():
			if key.startswith('docker_network') and len(key)>len("docker_network"):
				self.logger.debug('FOUND additional docker network '+key+'='+value+' to attach to container.')
				networknames=[]
				networknames.append(value)
				try:
					networks = dockerClient.networks.list(names=networknames)
					if networks!=None and len(networks)>0:
						self.logger.debug('found networks '+str(networks))
						# attached to network at [0]
						network=dockerClient.networks.get(networks[0].id)
						self.logger.debug('attaching to network '+str(network))
						network.connect(self.container)
						
						self.container.reload()
						self.logger.debug('Attached to network '+network.name)
						self.logger.debug(self.container.attrs['NetworkSettings']['Networks'][network.name])
						ipaddrProp="docker_ipaddr"+key[len("docker_network"):]
						if ipaddrProp in self.properties:
							self.logger.debug('setting read only property '+ipaddrProp)					
							self.properties[ipaddrProp]=self.container.attrs['NetworkSettings']['Networks'][network.name]['IPAddress']
					
				except docker.errors.APIError:
					self.logger.error('could not find network '+networkname)
					self.logger.error('set error in db')
					

		

	def runTransition(self, cmd, properties=None,isTransition=True):
		self.logger.info('running transition command '+cmd)

		self.logger.debug("update all property environment variables in the container?")

		cmdList=[]
		cmdList.append(cmd)
		
		""" get the running container """
		if self.container==None:
			self.container=self.getContainer()

		if self.container!=None:
			self.logger.debug('found container and running command')

			""" run command """
			self.logger.info('***TRANSITION: '+str(cmdList)+' created on RESOURCE: '+ self.name +'***')

			# update properties on the container before we call command
			self.sendProperties(properties,isTransition)

			resp=self.container.exec_run(cmdList, stream=True)
			self.logger.info('***CMD OUTPUT from resource: '+self.name+' ***')
			for val in resp:
				self.logger.info('*** >>>>>>'+str(val))

			# collect any property changes after command runs
			self.getProperties()
			self.logger.info('***TRANSITION: '+str(cmdList)+' complete on RESOURCE: '+ self.name +'***')

		else:
			self.logger.error('no running container found')
			return None

		# update container ids in instance and transition?
		ret={'status':'OK','containerId':self.container.id}
		return ret

	def sendProperties(self,properties=None,transition=True):
		# send properties as a yaml string to container using docker exec
		# store yaml in /etc/rmparams
		if properties!=None:
			props=properties
		else:
			props=self.properties
			
		self.logger.info('Sending properties '+str(props))

		propString=yaml.dump(props,default_flow_style = False,default_style='')
		if transition:
			cmdString="/bin/sh -c \"echo '"+propString+"' > /etc/rmparams\""
		else:
			cmdString="/bin/sh -c \"echo '"+propString+"' > /etc/opparams\""
			
		self.logger.debug(cmdString)
		resp=self.container.exec_run(cmdString, stream=True)

	def getProperties(self):
		# cat the current /etc/rmparams file on container
		# update the properties on this object and store
		self.logger.debug('Retrieving properties from container')
		resp=self.container.exec_run("cat /etc/rmparams", stream=True)
		
		propYaml=None
		for val in resp:
			propYaml=yaml.safe_load(val)
			self.logger.debug('updating properties with '+str(propYaml))
			
		#loop over resource instance properties and update if changes found, else ignore
		for p in self.properties:
			if p in propYaml:
				self.logger.debug('updating resource property:'+p+' with value '+str(propYaml[p]))
				self.properties[p]=propYaml[p]
				
		self.logger.info('Updated properties '+str(self.properties))

	def getContainer(self) :
		containername='dockerrm-'+self.type.imageName+str(self.resourceId)
		self.logger.debug('getting container '+containername)
		try:
			c=dockerClient.containers.get(containername)
			return c
		except docker.errors.NotFound:
			self.logger.error('cannot find container')
		except docker.errors.APIError:
			self.logger.error('cannot connect to server')

	def getID(self):
		self.logger.debug('getting container instance id')
		id = None
		if self.container != None:
			id = self.container.id
		return id

	def runStandardTransition(self, transitionName, properties):
		self.logger.debug('running standard transition '+transitionName)
		self.logger.debug(properties)

		if transitionName=='uninstall':
			self.logger.debug('about to kill container')
			try:
				if 'lifecycle' in self.type.lifecyclePath and transitionName in self.type.lifecyclePath['lifecycle']:
					self.runTransition(self.type.lifecyclePath['lifecycle'][transitionName])

				self.logger.debug('killing container')
				self.container.kill()
				self.container.remove()

				#remove resource instance from the list
				removeResourceInstance(self.resourceId)

				ret={'status':'OK'}
			except docker.errors.APIError:
				ret={'status':'Failed'}
			return ret

		if transitionName=='install':
			self.logger.debug('creating container for install transition')
			""" start a new container """
			self.startContainer()

		""" now run script """
		self.logger.debug('about to run lifecycle script')
		self.logger.debug(self.type.lifecyclePath)
		if self.type!=None and self.type.lifecyclePath!=None:
			if 'lifecycle' in self.type.lifecyclePath and transitionName in self.type.lifecyclePath['lifecycle']:
				self.logger.debug('running '+self.type.lifecyclePath['lifecycle'][transitionName]+' from lifecycle config')
				return self.runTransition(self.type.lifecyclePath['lifecycle'][transitionName])
		else:
			self.logger.error('no lifecycle config found for transition '+transitionName)
			return None

	def runAddNetworkOperation(self,properties):
		self.logger.debug('adding network with properties '+str(properties))

		networkid=properties['networkid']
		if networkid==None:
			self.logger.error('no network id provided')
			return None

		network=dockerClient.networks.get(networkid);

		# attach this container to network
		if self.container!=None:
			network.connect(self.container)
		else:
			self.logger.error('no container found to attach to network')
			return None

		ret={'status':'OK','containerId':self.container.id}
		return ret

	def runRemoveNetworkOperation(self,properties):
		self.logger.debug('removing network with properties '+str(properties))

		networkid=properties['networkid']
		if networkid==None:
			self.logger.error('no network id provided')
			return None

		network=dockerClient.networks.get(networkid);

		if self.container!=None:
			network.disconnect(self.container)
		else:
			self.logger.error('no container found to detach from network')
			return None
		
		ret={'status':'OK','containerId':self.container.id}
		return ret

	def runOperation(self, transitionName,properties):
		self.logger.debug('running operation '+transitionName +' with properties '+str(properties))

		if transitionName=='addNetwork':
			self.logger.debug('calling default add network operation on resource '+self.name)
			return self.runAddNetworkOperation(properties)

		elif transitionName=='removeNetwork':
			self.logger.debug('calling default remove network operation on resource '+self.name)
			return self.runRemoveNetworkOperation(properties)

		else:
			""" run resource operation script """
			self.logger.debug('about to run operation script')
			self.logger.debug(self.type.operationsPath)
			if self.type!=None and self.type.operationsPath!=None:
				if 'operations' in self.type.operationsPath and transitionName in self.type.operationsPath['operations']:
					self.logger.debug('running '+self.type.operationsPath['operations'][transitionName]+' from operations config')
					return self.runTransition(self.type.operationsPath['operations'][transitionName], properties,False)
			else:
				self.logger.error('no operations config found for operation '+transitionName)
				return None
	
	def getInstanceStatus(self):
		self.logger.debug('get running instance status')
		return {
				 'resourceId':self.resourceId,
				 'resourceType':self.type.name,
				 'resourceName': self.name,
				 'createdAt': self.createdAt,
				 'properties':self.properties,
				 'deploymentLocation':self.location,
				 'lastModifiedAt':self.lastModifiedAt,
				 'resourceManagerId':globalConfig.configDescriptor['name']
				 } 

	def getInstanceDetails(self):
		self.logger.debug('get running instance details')
		internalContainers=[]
		if self.container!=None:
			container={
				'id':self.container.id,
				'name': self.container.name,
				'type':'docker container'
			}
			internalContainers.append(container)

		return {
				 'resourceId':self.resourceId,
				 'resourceType':self.type.name,
				 'resourceName': self.name,
				 'createdAt': self.createdAt,
				 'properties':self.properties,
				 'deploymentLocation':self.location,
				 'lastModifiedAt':self.lastModifiedAt,
				 'resourceManagerId':globalConfig.configDescriptor['name'],
				 'internalResourceInstances':internalContainers
				 } 		

##########################################################################################
# Resource instance exceptions
##########################################################################################

# could not find a docker image for resource
class NoImageException (Exception):
	def __init__(self, id):
		self.id=id

# could not find a running container
class NoContainerException (Exception):
	def __init__(self, id):
		self.id=id

# could not find the requested resource instance
class InstanceNotFoundException(Exception):
	def __init__(self, id):
		self.id=id