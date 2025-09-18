from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger
from sygra.recipes.evol_instruct.instruct_mgr import get_instruction


# input is `text` and output is `evol_instruct_final_prompt`
class EvolInstructPromptGenerator(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        text = state.get("text")
        algorithm = state.get("algorithm")
        algorithm = "random" if algorithm is None else algorithm
        final_prompt = get_instruction(text, algorithm)
        logger.debug(f"Evol instruct final input prompt: {final_prompt}")
        # Simple return can also work without output_keys definition in yaml file
        # return {"evol_instruct_final_prompt": final_prompt}
        state["evol_instruct_final_prompt"] = final_prompt
        return state
