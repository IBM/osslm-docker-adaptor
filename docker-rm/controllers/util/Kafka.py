import logging
import json
from kafka import KafkaProducer
from controllers.util.Config import *

class Kafka:
	def __init__(self):
		self.logger= logging.getLogger(__name__)

		# producer set to None by default unless global config sets to active
		self.producer=None

		self.logger.debug(globalConfig.configDescriptor['supportedFeatures'])
		if 'asynchronousTransitionResponse' in globalConfig.configDescriptor['supportedFeatures']:
			self.logger.debug('FOUND IT')

		#get the address of the kafka servers if it is set to active in config.yaml and create a producer
		if globalConfig.configDescriptor["supportedFeatures"]["asynchronousTransitionResponse"]==True:
			self.logger.debug('trying to configure Kafka')
			try:
				self.logger.debug('kafka is set to Active - trying to create kafka producer on '+globalConfig.configDescriptor['properties']['responseKafkaConnectionUrl'])
				self.producer = KafkaProducer(bootstrap_servers=globalConfig.configDescriptor['properties']['responseKafkaConnectionUrl'])
			except Exception as e:
				#self.logger.error(e.__class__.__name__)
				self.logger.error('could not connect to kafka server at '+globalConfig.configDescriptor['properties']['responseKafkaConnectionUrl']+' no messages will be published')
				self.producer=None

		else:
			self.logger.debug('kafka not set to active - no messages will be published')

	def sendLifecycleEvent(self, msg):
		self.logger.debug('sending message to kafka '+str(msg))

		# if have a valid producer then send a kafka message, otherwise do nothing
		if self.producer!=None:
			self.logger.debug('have valid producer')

			topic = globalConfig.configDescriptor['properties']['responseKafkaTopicName']

			self.logger.debug("sending transition event to Kafka topic "+topic)

			future = self.producer.send(topic, json.JSONEncoder().encode(msg).encode('utf-8'))

			try:
			    record_metadata = future.get(timeout=10)
			except KafkaError:
			    log.exception()
			    pass
		else:
			self.logger.debug('no valid kafka producer found')

	def sendMetric(self):
		self.logger.debug("TODO____----- implment sending metric to kafka")

kafkaClient=Kafka()