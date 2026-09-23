from lp_agent.main import LPAgent


class AgentChecker:
    def __init__(self, agent: LPAgent):
        self._agent = agent

    @classmethod
    def check_upl(cls, output: str):
        check_passed = True
        # TODO: run an algorithmic check of the output against UPL rules. Set pass to False if UPL found.
        if not output:
            check_passed = False
        return check_passed

        @classmethod
        def check_finished(cls, output: str):
            check_passed = True
            percent_complete = 0
            # TODO: run an algorithmic check to see if the conversation has progressed through all phases.
            if not output:
                check_passed = False
            return check_passed, percent_complete
