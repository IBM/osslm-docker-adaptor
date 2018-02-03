import logging
from controllers.transition.TransitionTasks import TransitionTask


class IntegrityTransitionTask(TransitionTask):
    def __init__(self, transition, instance):
        super().__init__(transition, instance)
        self.logger = logging.getLogger(__name__)

    def run(self):
        super().run('integrity')
