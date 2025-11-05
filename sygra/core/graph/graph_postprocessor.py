from abc import ABC, abstractmethod


class GraphPostProcessor(ABC):
    """
    Post-processor for whole graph level, not the node level
    Important: do not use graph level post processor for large amount of data generation as it is memory inefficient
    """

    @abstractmethod
    def process(self, data: list, metadata: dict) -> list:
        # implement post processing logic with whole data, return the final data list
        pass