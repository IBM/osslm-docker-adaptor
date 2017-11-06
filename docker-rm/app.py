#!/usr/bin/env python3

import connexion
import os
import logging.config
import yaml
from controllers.util.Config import *
from controllers.util.Trace import *

def setup_logging(default_path='config/logging.yaml', default_level=logging.INFO):
	path = default_path
	if os.path.exists(path):
		with open(path, 'rt') as f:
			config = yaml.safe_load(f.read())
		logging.config.dictConfig(config)
	else:
		logging.basicConfig(level=default_level)	

if __name__ == '__main__':
	setup_logging()
	globalConfig.read()
	setupTrace()
	app = connexion.App(__name__, specification_dir='./swagger/')
	app.add_api('swagger.yaml', arguments={'title': 'Docker Resource Manager Reference Implementation'})
	app.run(port=8081,server='gevent')
