from core.graph.functions.lambda_function import LambdaFunction
from core.graph.grasp_state import GraspState
from logger.logger_config import logger
from processors.output_record_generator import BaseOutputGenerator
from recipes.evol_instruct.instruct_mgr import get_instruction


# input is `text` and output is `evol_instruct_final_prompt`
class EvolInstructPromptGenerator(LambdaFunction):
    def apply(lambda_node_dict: dict, state: GraspState):
        text = state["text"]
        algorithm = state.get("algorithm")
        algorithm = "random" if algorithm is None else algorithm
        final_prompt = get_instruction(text, algorithm)
        logger.debug(f"Evol instruct final input prompt: {final_prompt}")
        # Simple return can also work without output_keys definition in yaml file
        # return {"evol_instruct_final_prompt": final_prompt}
        state["evol_instruct_final_prompt"] = final_prompt
        return state
