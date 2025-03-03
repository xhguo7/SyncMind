"""
React eval: evaluate agent's out-of-sync cause localization
"""

from pandas import Series

class ReactEvaluator:
    def __init__(
            self, 
            instance: Series,
            agent_answer: str
        ) -> None:
        self.agent_answer = self.parse_agent_answer(agent_answer)
        self.instance = instance

    def parse_agent_answer(self, agent_answer: str) -> str:
        """Parse answer"""
        if agent_answer:
            agent_answer = agent_answer.strip()
        return agent_answer

    def agent_message_react_eval(self):
        """React eval"""
        gt_absolute_pyfile_path = "/workspace/test_repo" + self.instance.pyfile_path.split("test_repo")[1]
        gt_fm_name = self.instance.fm_name
        gold_react = f"{gt_absolute_pyfile_path}\n{gt_fm_name}"
        react_grade = 0

        if not self.agent_answer:
            return react_grade
        
        if gold_react in self.agent_answer:
            react_grade = 1
        if (gt_absolute_pyfile_path in self.agent_answer) and (gt_fm_name in self.agent_answer):
            react_grade = 1
        return react_grade
