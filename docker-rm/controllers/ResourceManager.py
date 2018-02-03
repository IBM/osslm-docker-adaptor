import logging
from pathlib import Path
from controllers.resource import Resource
from controllers.resource.DockerNetworkResourceInstance import DockerNetworkResourceInstance
import controllers.resource.ResourceInstance
import controllers.util.DB
from controllers.transition.Transition import *
from controllers.util.Config import *
from controllers.transition.TransitionTasks import MissingPropertiesException, findInstanceByResourceId


class ResourceManager:
    # Main helper class for managing resource types, transitions and resource instances

    def __init__(self):
        # initialise resource manager by reading available types
        # instances of special docker resource types such as networks are also read on init
        # user specified types are read from the default csars directory

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Creating Resource Manager')

        # list of resources
        self.resources = []

        # load all internal types
        self.readResourceDir('internal_csars', True)
        # search for existing docker network instances and create resource instances
        self.buildReferencedNetworkInstances()
        # read user supplied resource type directory
        if 'csardirs' in globalConfig.configDescriptor:
            for dir in globalConfig.configDescriptor['csardirs']:
                self.readResourceDir(dir)

    def buildReferencedNetworkInstances(self):
        # load all existing docker networks as referenced external network instances

        self.logger.debug('creating reference docker network resource instances')

        if controllers.resource.ResourceInstance.dockerClient is not None:
            self.logger.debug('found valid dockerClient - loading networks')
            netType = self.getResourceType('resource::docker-network::1.0')
            if netType is not None:
                networks = controllers.resource.ResourceInstance.dockerClient.networks.list()
                for n in networks:
                    self.logger.debug('creating resource instance for existing docker network ' + n.name)
                    refNet = DockerNetworkResourceInstance(netType, n.name, network=n)
            else:
                self.logger.error('no reference network type found')

    def reloadResourceDir(self):
        self.resources = []
        self.readResourceDir('internal_csars', True)
        if 'csardirs' in globalConfig.configDescriptor:
            for dir in globalConfig.configDescriptor['csardirs']:
                self.readResourceDir(dir)
        return self.getResourceTypeList()

    def readResourceDir(self, dirname, internal=False):
        self.logger.debug('reading resource dir ' + dirname)
        # look in csars directory for user defined resource
        p = Path(dirname)
        for cpath in p.iterdir():
            if cpath.is_dir():
                self.logger.debug('found ' + cpath.name)
                if cpath.name != 'baseimage':
                    if self.getResourceType(cpath.name) is None:
                        self.logger.debug('loading new resource type ' + cpath.name)
                        r = Resource(cpath, internal)
                        self.resources.append(r)
                    else:
                        self.logger.debug('resource already exists -> not adding')
            else:
                self.logger.debug('ignoring file ' + str(cpath))

    def createNewResourceInstance(self, resourceType, name, location, params):
        self.logger.debug(resourceType)
        self.logger.debug(
            'creating new resource instance of type ' + resourceType.name + ' in location ' + location + ' with name ' + name)
        self.logger.debug(params)
        # create a new resource instance

        if resourceType.name == 'resource::docker-network::1.0':
            self.logger.debug('creating a special docker network type')
            # check if the network already exists, if it does then pass back existing resource instance
            # find the network
            self.logger.debug('looking for existing network')
            # networkName is mandatory
            if 'networkname' not in params:
                raise MissingPropertiesException('networkname')
            instance = controllers.resource.ResourceInstance.findInstancesByLocation(location, params['networkname'],
                                                                                     resourceType.name)
            if instance is None:
                self.logger.debug('no network so create a new docker network')
                # network does not exist so create it
                resourceInstance = DockerNetworkResourceInstance(
                    resourceType,
                    name,
                    location,
                    params)
            else:
                # network exists so return that resourceInstance
                self.logger.debug('returning existing network')
                return instance
        else:
            resourceInstance = ResourceInstance(resourceType,
                                                name,
                                                location,
                                                params)

        return resourceInstance

    def findInstanceById(self, id):
        self.logger.debug('finding instance with id ' + id)

        try:
            instance = findInstanceByResourceId(id)
            return instance
        except Exception:
            return None

    def searchForInstances(self, location, typename):
        self.logger.debug('searching for instances in ' + location)
        if typename is not None:
            self.logger.debug('with typename ' + typename)

        instances = findInstances(location, typename)

        return instances

    def rejectIfResourceBusy(self, transitionRequest):
        self.logger.debug('Checking that resource is not currently processing a transition ' + str(transitionRequest))
        if 'resourceId' in transitionRequest:
            resourceId = transitionRequest['resourceId']
            transitions = dbClient.findTransitionsByResourceID(int(resourceId))
            for transition in transitions:
                if transition is not None:
                    self.logger.debug('Found existing transition:'
                                      + str(transition['requestId']) + ' '
                                      + str(transition['requestState']))
                    if transition['requestState'] == 'IN_PROGRESS':
                        resource = self.findInstanceById(resourceId)
                        message = 'Rejecting ' + transitionRequest[
                            'transitionName'] + ' on ' + resource.name + ' (resourceId: ' + resourceId + ') - a transition is already IN_PROGRESS'
                        self.logger.error(message)
                        raise ResourceBusyException(message)
                else:
                    self.logger.debug('Resource id given, but no transitions found in DB')
        else:
            self.logger.debug('no resource id found, assuming an install request')

    def runTransition(self, transitionRequest):
        """ run transition on new or existing instance """
        self.logger.debug('Resource Manager runTransition called with request\n\n ' + str(transitionRequest) + '\n\n')

        # self.rejectIfResourceBusy(transitionRequest)

        """ run the transition and parse input parameters"""
        transition = Transition(transitionRequest)

        try:
            response = transition.runTransition()
            return response
        except Exception as ex:
            self.logger.error(str(ex))
            transition.delete()
            raise ex

    def getTransitionRequest(self, id):
        self.logger.debug('get transition request for id ' + id)
        # find id for transition in database
        transitionRequest = dbClient.findTransitionByRequestID(int(id))
        self.logger.debug(transitionRequest)

        if transitionRequest is None:
            return {'error': 'no transition found'}

        return transitionRequest

    def getTransitionStatus(self, id):
        self.logger.debug('get transition status for id ' + id)

        # find id for transition in database
        transitionRequest = dbClient.findTransitionByRequestID(id)
        self.logger.debug(transitionRequest)

        if transitionRequest is None:
            return {'error': 'no transition found'}

        # return Transition Status
        self.logger.debug('need to update this to return status not actual db object')
        return transitionRequest

    def getResourceType(self, typename):
        self.logger.debug('get resource type info for ' + typename)

        for i in self.resources:
            if i.name == typename:
                self.logger.debug('found ' + typename + ' returning overview')
                return i

        self.logger.debug(typename + ' not found')
        return None

    def getResourceTypeDetails(self, typename):
        self.logger.debug('get resource type info for ' + typename)

        for i in self.resources:
            if i.name == typename:
                self.logger.debug('found ' + typename + ' returning overview')
                return i.getResourceDetails()

        self.logger.debug(typename + ' not found')
        return {'error': typename + ' not found'}

    def getResourceTypeList(self):
        self.logger.debug("get type list")
        typelist = []

        for i in self.resources:
            typelist.append(i.getResourceOverview())

        self.logger.debug(typelist)

        return typelist


##########################################################################################
# Resource manager exceptions
##########################################################################################

# cannot find type
class TypeNotFoundException(Exception):
    def __init__(self, type):
        self.type = type


# transition request does not contain a type
class TypeMissingFromRequestException(Exception):
    pass


# resource instance cannot be found
class InstanceNotFoundException(Exception):
    def __init__(self, id):
        self.id = id


#
class InvalidTransitionException(Exception):
    def __init__(self, transition):
        self.transition = transition


class NoLocationInRequestException(Exception):
    pass


class UnknownLocationInRequestException(Exception):
    def __init__(self, unknownLocation):
        self.unknownLocation = unknownLocation


class ResourceBusyException(Exception):
    def __init__(self, message):
        self.message = message


""" -------------------------------=
    global resource manager variable 
	================================
"""
resourceManager = ResourceManager()
