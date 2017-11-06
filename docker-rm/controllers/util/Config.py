import logging
import yaml

class Config:
	def __init__(self):
		self.logger = logging.getLogger(__name__)
		self.configDescriptor={}
		self.locationDescriptor={}

	def read(self):
		self.logger.debug('reading global configuration')

		with open('config/config.yaml', 'rt') as f:
			self.configDescriptor = yaml.safe_load(f.read())
			self.logger.debug(self.configDescriptor)

		with open('config/locations.yaml', 'rt') as f:
			self.locationDescriptor = yaml.safe_load(f.read())
			self.logger.debug(self.locationDescriptor)

		self.logger.debug('perform validation on confg descriptor, make sure it has all bits required for kafka etc')

globalConfig=Config()