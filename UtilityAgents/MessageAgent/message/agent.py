from __future__ import absolute_import

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core


utils.setup_logging()
log = logging.getLogger(__name__)


class MessageAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(MessageAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.topic = config.get("topic", "actuate")
        self.value = config.get("value", 0)

    @Core.receiver('onstart')
    def start_message(self, sender, **kwargs):
        self.vip.pubsub.publish('pubsub', self.topic, headers={}, message=self.value).get(timeout=5.0)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(MessageAgent)
    except Exception as e:
        log.exception(e)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
