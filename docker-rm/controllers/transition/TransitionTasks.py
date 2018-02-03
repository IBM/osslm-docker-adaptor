import logging
import re
import threading
from datetime import datetime, timezone
# from controllers.util.DB import *
from controllers.resource.ResourceInstance import *
from controllers.util.Kafka import *
from controllers.transition.Transition import *
from controllers.util.DB import *

lock = threading.Lock()


class TransitionTask(threading.Thread):

    def __init__(self, transition, resourceInstance=None):

        threading.Thread.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.logger.info(
            'new transition task thread with transition ' + str(transition.transitionName) + ' and instance ' + str(
                resourceInstance))
        self.transition = transition
        self.resourceInstance = resourceInstance
        self.logger.debug('finished init of transition task')

    def validateOperationProperties(self, operationName, resourceType):
        self.logger.debug('validating operation ' + operationName + ' properties')
        if operationName == 'addNetwork' or operationName == 'removeNetwork':
            self.logger.debug('found standard network operations')
            return self.validateProps({
                'networkid': {
                    'type': 'string'
                }
            })

        if resourceType is not None:
            self.logger.debug('resource properties are ' + str(resourceType.resourceDescriptor['properties']))
            # loop over type properties and make sure all are in transition if not defaulted
            return self.validateProps(resourceType.resourceDescriptor['operations'][operationName]['properties'])

    def validateStandardProperties(self, resourceType):
        # validate all properties are present, returns boolean
        self.logger.debug('validating properties on transition ' + str(self.transition.properties))
        if resourceType is not None:
            self.logger.debug('resource properties are ' + str(resourceType.resourceDescriptor['properties']))
            # loop over type properties and make sure all are in transition if not defaulted
            resp = self.validateProps(resourceType.resourceDescriptor['properties'])
            return resp

    def validateProps(self, props):
        self.logger.debug('validating properties')
        # guard against no properties section at all, there may still be optional properties in descriptor
        transitionProperties = {}
        if hasattr(self.transition, 'properties'):
            transitionProperties = self.transition.properties

        if transitionProperties is None:
            transitionProperties = {}

        self.logger.debug('Properties to validate against descriptor: ' + str(transitionProperties))
        self.logger.debug('Properties from descriptor: ' + str(props))
        if props is None:
            self.logger.error('no properties found')
            return False

        for p in props:
            self.logger.debug('validating ' + str(p))
            if 'default' in props[p] and p in transitionProperties:
                self.logger.debug('default value overridden so pass')
                pass
            elif 'default' in props[p] and p not in transitionProperties:
                self.logger.debug('default value for ' + str(p)
                                  + ' not overridden, setting default value ' + str(props[p]['default'])
                                  + ' in transition properties')
                transitionProperties[p] = props[p]['default']
                pass
            elif 'value' in props[p]:
                self.logger.debug('value provided so pass')
                pass
            elif 'read-only' in props[p] and props[p]['read-only'] is True:
                self.logger.debug('read only value so pass')
                pass
            elif p in transitionProperties:
                self.logger.debug('found it')
            elif 'required' not in props[p]:
                self.logger.debug('property is missing but not required so pass')
                pass
            elif 'required' in props[p] and props[p]['required'] is False:
                self.logger.debug('property is missing but not required = False so pass')
                pass
            else:
                self.logger.error('missing property ' + p)
                raise controllers.transition.TransitionTasks.MissingPropertiesException(p)

        return True

    def checkExistingNetwork(self):
        self.logger.debug("checking if this is a network type, if it exists and if it is read only")

        if self.resourceInstance.type.name == "resource::docker-network::1.0" and self.resourceInstance.readonly is True:
            self.logger.debug('existing read only network found')
            return True

        self.logger.debug('not existing readonly network')
        return False

    def reportFailedTask(self, reason):
        self.logger.debug('Failed task - updating DB with failure and error')
        self.transition.requestState = 'FAILED'
        self.transition.requestStateReason = reason
        self.transition.finishedAt = str(datetime.now(timezone.utc).astimezone().isoformat())

    def run(self, transitionName, standardLifecycle=True):
        self.logger.debug('run transition ' + transitionName
                          + ' resource id: ' + str(self.transition.resourceId)
                          + ' request id: ' + str(self.transition.requestId))
        resp = None

        # if this is a read only network then just return true
        if self.checkExistingNetwork():
            self.logger.debug('mark install complete for pre-existing network')
            self.transition.requestState = 'COMPLETED'
            self.transition.finishedAt = str(datetime.now(timezone.utc).astimezone().isoformat())
        else:
            try:
                if standardLifecycle is True:
                    self.logger.debug('running standard transition ' + transitionName)
                    resp = self.resourceInstance.runStandardTransition(transitionName, self.transition.properties)
                else:
                    self.logger.debug('running operation ' + transitionName)
                    with lock:
                        self.logger.debug('Locked for  transition ' + transitionName
                                          + ' resource id: ' + str(self.transition.resourceId)
                                          + ' request id: ' + str(self.transition.requestId))
                        resp = self.resourceInstance.runOperation(transitionName, self.transition.properties)
                        self.logger.debug('Unlocked for  transition ' + transitionName
                                          + ' resource id: ' + str(self.transition.resourceId)
                                          + ' request id: ' + str(self.transition.requestId))
                self.logger.debug('marking transition COMPLETED')
                self.transition.requestState = 'COMPLETED'
                self.transition.finishedAt = str(datetime.now(timezone.utc).astimezone().isoformat())
            except Exception as ex:
                self.logger.error('caught transition exception ' + str(type(ex).__name__) + ' ' + str(ex))

                resp = None
                self.reportFailedTask("Failure from Virtual Infrastructure: " + str(ex))

            self.logger.debug(resp)

        if self.transition.resourceId is None:
            self.logger.debug('adding resource id to transition object')
            self.transition.resourceId = self.resourceInstance.resourceId

        # update the transition in database
        self.logger.debug('updating transition status in database')
        with lock:
            self.transition.updateDB()

        # Get the createdAt for the resource
        createdAt = self.transition.finishedAt

        if self.transition.transitionName.lower() != 'install':
            with lock:
                # Query the database to find when this resource was installed
                dbTransitions = dbClient.findTransitionsByResourceID(self.resourceInstance.resourceId)
                if dbTransitions is not None:
                    for dbTransition in dbTransitions:
                        if 'transitionName' in dbTransition and dbTransition['transitionName'].lower() == 'install':
                            createdAt = dbTransition['finishedAt']

        # send update to kafka
        kafkaMessage = self.transition.getTransitionRequestStatus()

        internalResourceInstance = {
            'name': self.resourceInstance.name,
            'type': re.sub('[:.-]', '_', self.resourceInstance.type.name),
        }
        if self.resourceInstance.type.name == "resource::docker-network::1.0":
            if 'networkid' in self.resourceInstance.properties:
                internalResourceInstance['id'] = self.resourceInstance.properties['networkid']
        else:
            internalResourceInstance['id'] = self.resourceInstance.getID()

        resourceInstance = {
            'resourceId': self.resourceInstance.resourceId,
            'metricKey': self.transition.metricKey,
            'resourceName': self.resourceInstance.name,
            'resourceType': self.resourceInstance.type.name,
            'resourceManagerId': self.transition.resourceManagerId,
            'deploymentLocation': self.transition.deploymentLocation,
            'properties': self.resourceInstance.properties,
            'createdAt': createdAt,
            'lastModifiedAt': self.transition.finishedAt,
            'internalResourceInstances': [internalResourceInstance],
        }
        kafkaMessage['transitionName'] = self.transition.transitionName
        kafkaMessage['resourceManagerId'] = self.transition.resourceManagerId
        kafkaMessage['deploymentLocation'] = self.transition.deploymentLocation
        kafkaMessage['resourceInstance'] = resourceInstance

        self.logger.info('completed task ' + str(self.transition.requestId) + ' with response =' + str(kafkaMessage))
        kafkaClient.sendLifecycleEvent(kafkaMessage)


class NoTransitionFoundException(Exception):
    def __init__(self, requestId):
        self.requestId = requestId


class MissingPropertiesException(Exception):
    def __init__(self, missingProperty):
        self.missingProperty = missingProperty
