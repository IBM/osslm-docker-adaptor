import logging
from controllers.transition.TransitionTasks import TransitionTask


class OperationTransitionTask(TransitionTask):
    # class to validate and run operations on resource instances
    def __init__(self, transition, instance):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('new operation task created')

        super().__init__(transition, instance)

        # check the resoucee desciptor for value operations and expected parameters
        self.logger.debug(self.resourceInstance.type.resourceDescriptor)

        super().validateOperationProperties(self.transition.transitionName, instance.type)

    def run(self):
        super().run(self.transition.transitionName, False)
