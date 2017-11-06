import logging
import json
from controllers.ResourceManager import *
from controllers.resource.Resource import Resource
from controllers.util.Config import *
from controllers.util.Trace import *
from controllers.resource.ResourceInstance import InstanceNotFoundException
from controllers.util.DB import DBException

logger = logging.getLogger(__name__)

def get_configuration_using_get() -> str:
	# retrieve resource manager global configuration
	logger.debug('return global configuration')
	
	traceMessage("Get Configuration","None",globalConfig.configDescriptor)
	return globalConfig.configDescriptor,200

def getFormattedErrorMessage(message, url = None, details = None):
	message = {'localizedMessage': message}
	if url != None:
		message['url'] = url
	if details != None:
		message['details'] = {'detail': details}
		
	logger.error('returning error message: ' + str(message))
	return message
	
	
def create_transition_using_post(transitionRequest) -> str:
	# request a transition on existing or new resource instances 
	logger.info("New transition request with payload "+str(transitionRequest))
	endpoint = '/api/resource-manager/lifecycle/transitions'
	try:
		resp=resourceManager.runTransition(transitionRequest)
		
		traceMessage("POST Transition",transitionRequest,resp)
		return resp,202
		
	except TypeNotFoundException as ex:
		return getFormattedErrorMessage('type not found '+ex.type, endpoint), 400
	
	except NoLocationInRequestException as ex:
		return getFormattedErrorMessage('no location included in the request', endpoint), 400
	
	except UnknownLocationInRequestException as ex:
		return getFormattedErrorMessage('Unknown location "' + ex.unknownLocation + '" in request', endpoint), 404
	
	except TypeMissingFromRequestException:
		return getFormattedErrorMessage('type parameter required but not found', endpoint), 400
		
	except InstanceNotFoundException as ex:
		return getFormattedErrorMessage('Resource instance '+ str(ex.id) + ' not found', endpoint ), 404
	
	except InvalidTransitionException as ex:
		return getFormattedErrorMessage('Invalid transition '+ str(ex.transition), endpoint ), 400
	
	except MissingPropertiesException as ex:
		return getFormattedErrorMessage('Missing mandatory property: ' + str(ex.missingProperty), endpoint), 400
	
	except ResourceBusyException as ex:
		return getFormattedErrorMessage(str(ex.message), endpoint), 400
	
	except DBException as ex:
		return getFormattedErrorMessage(str(ex.message), endpoint), 500
	
	except Exception as ex:
		template = 'An exception of type {0} occurred. Arguments:{1!r}'
		message = template.format(type(ex).__name__, ex.args)
		logger.error(message)
		return getFormattedErrorMessage(message, endpoint), 500
		
		
def get_transition_status_using_get(id) -> str:
	# return detailed status of transition request
	logger.debug('get transition status for id '+id)

	resp=resourceManager.getTransitionStatus(id)
	logger.debug(resp)

	traceMessage("GET Transition Status1",id, resp)
	responseCode = 200
	if 'error' in resp:
		responseCode = 404
	return resp, responseCode

def get_transition_using_get(id) -> str:
	# get a transition request status by its request ID
	logger.debug('get transition request for id '+id)

	""" return current status of transition id """
	resp=resourceManager.getTransitionRequest(id)
	logger.debug(resp)

	traceMessage("GET Transition Status2",id, resp)
	responseCode = 200
	if 'error' in resp:
		responseCode = 404
	return resp, responseCode
	

def get_deployment_location_using_get(name) -> str:
	# get specific deployment location and return details
	logger.debug('get deployment location for '+name)
	logger.debug(globalConfig.locationDescriptor)

	for i in globalConfig.locationDescriptor['locations']:
		if i['name']==name:
			resp={'name':name,
					'type':i['type']}
			traceMessage("GET deployment location by name",name, resp)
			return resp,200

	traceMessage("GET deployment location by name",name, 'no such location')
	return getFormattedErrorMessage('no such location ' + str(name), endpoint), 404

def get_deployment_locations_using_get() -> str:
	# return all deployment locations this resource manager is configured to support
	logger.debug('Getting deployment locations')
	logger.debug(globalConfig.locationDescriptor)

	locations=[]
	for l in globalConfig.locationDescriptor['locations']:
		logger.debug(l)
		loc={
			'name':l['name'],
			'type':l['type']
		}
		locations.append(loc)

	traceMessage("GET deployment locations","None", locations)
	return locations,200

def get_instance_using_get(id) -> str:
	logger.debug('find instance with resource id '+id)

	try:
		# look for instances with id
		instance=resourceManager.findInstanceById(id)
		resp={}
		if instance !=None:
			logger.debug('instance status')
			resp=instance.getInstanceDetails()
			logger.debug(resp)
		else:
			return {'error':'instance is null'}
	except Exception as ex:
		logger.error(ex)
		logger.error('SOMETHING BAD - TODO replace with more exceptions')
		return getFormattedErrorMessage('no instances found', endpoint), 404
		
	traceMessage("GET instance by id",id, resp)
	return resp

def get_instances_using_get(name, instanceType = None, relatedInstanceId = None, instanceName = None) -> str:
	""" search for running instances """
	logger.debug('search for instances')

	# check that the location name is valid
	for i in globalConfig.locationDescriptor['locations']:
		if i['name']==name:
			#filter by location, type, and related instance id
			resp=resourceManager.searchForInstances(name, instanceType)
			
			traceMessage("GET instance",name, resp)
			return resp,200
	traceMessage("GET instance by name",name, {'error':'no location found'})
	return getFormattedErrorMessage('no location found', endpoint), 404


def get_type_using_get(name) -> str:
	""" return type details for given name """
	logger.debug('get type '+name)
	if bool(name and name.strip()):
		""" get resourece for requested type """
		r=resourceManager.getResourceTypeDetails(name)
		if 'error' in r:
			logger.debug(name+' not found')
			return r,404
	else:
		logger.error('no type name found')
		return "Empty type name provided", 404
		
	traceMessage("GET type",name, r)
	return r,200

def get_types_using_get() -> str:
	""" return list of all available types """
	logger.debug('get all types')
	
	list=resourceManager.getResourceTypeList()
		
	traceMessage("GET types","None", list)
	return list,200


def reload_resource_descriptors_using_put() -> str:
	""" reload all resource descriptors """
	logger.debug('reload all resource descriptors')
	resourceTypes = resourceManager.reloadResourceDir()
	
	return resourceTypes, 200
