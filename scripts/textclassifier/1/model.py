

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types import Concept

def concept_to_dict(concept: Concept) -> dict:
    return {"id": concept.id, "name": concept.name, "value": concept.value}

class TextClassifierModel(ModelClass):

    def load_model(self):
        pass

    @ModelClass.method
    def predict(self, text: str) -> list:
        # Example: dummy scores, replace with your model's output
        scores = {
            "safe": 0.99999999,
            "drug": 1e-08,
            "explicit": 1e-08,
            "gore": 1e-08,
            "suggestive": 1e-08
        }
        concepts = [Concept(name=k, value=v) for k, v in scores.items()]
        return [concept_to_dict(c) for c in concepts]
