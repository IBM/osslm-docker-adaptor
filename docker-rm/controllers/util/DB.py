from tinydb import TinyDB, Query
import logging
import threading

lock = threading.Lock()
class DB:
	""" persistence for instances and transition requests """
	def __init__(self) :
		self.logger = logging.getLogger(__name__)
		try:
			self.db = TinyDB('config/db.json')
			self.db.purge()
			self.db.purge_tables()
			
			self.transitionTable=self.db.table('transitions')
			#self.instanceTable=self.db.table('instances')
			
			self.logger.debug('created db at config/db.json')
		except Exception as ex:	
			raise DBException(ex)

	def createNewTransitionRequest(self,transition):
		""" store transition request and return unique id """
		self.logger.debug('create transition db entry called')
		self.logger.debug(transition)
		try:
			with lock:
				id=self.transitionTable.insert(transition)
			self.logger.debug('added transition request with id '+str(id))
		except Exception as ex:	
			raise DBException(ex)
		
		return id

	def updateTransitionRequest(self, id, transition):
		# update transition status
		self.logger.debug('update transition request')
		self.logger.debug(transition)
		try:
			with lock:
				self.transitionTable.update(transition,eids=[id])
		except Exception as ex:	
			raise DBException(ex)
		
	def removeTransition(self, eid):
		self.logger.debug('removing transition with eid '+str(eid))
		try:
			with lock:
				self.transitionTable.remove(eids=[eid])
		except Exception as ex:
			self.logger.error('cannot remove transition with eid '+str(eid))
			raise DBException(ex)

	def findTransitionByRequestID(self, id):
		# will need to be updated to reflect new transition stuff
		self.logger.debug('find transition db entry for request id '+str(id))
		Transition=Query()

		try:
			i=self.transitionTable.get(Transition.requestId==int(id))
		except Exception as ex:
			self.logger.error('something bad happened')
			raise DBException(ex)
		
		self.logger.debug(str(i))
		return i
	
	def findTransitionsByResourceID(self, id):
		self.logger.debug('search for transition db entry for resource id '+str(id))
		Transition=Query()
		transitions=[]
		try:
			transitions=self.transitionTable.search(Transition.resourceId==str(id))
		except Exception as ex:
			self.logger.error('something bad happened')
			raise DBException(ex)
		
		self.logger.debug(str(transitions))
		return transitions

	def findTransitionByID(self, id):
		# will need to be updated to reflect new transition stuff
		self.logger.debug('find transition db entry for id '+id)
		try:
			i=self.transitionTable.get(eid=int(id))
			self.logger.debug(i)
		except Exception as ex:
			self.logger.error('cannot find transition with eid '+str(eid))
			raise DBException(ex)
		
		return i

		
dbClient=DB()

# DB operation failure
	
class DBException (Exception):
	def __init__(self, ex):
		template = 'A database operation has failed of type {0}  {1!r}'
		self.message = template.format(type(ex).__name__, ex.args)
