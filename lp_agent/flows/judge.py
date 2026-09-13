
class AgentJudge:
  def __init__(self, environment, configuration):
    self.environment = environment
    self.configuration = configuration


  @classmethod
  def check_upl(self, output: str):
    check_passed = True
    # TODO: run a lightweight judge model to check the output against UPL rules. Set pass to False if UPL found.
    if not output:
      check_passed = False
    return check_passed
