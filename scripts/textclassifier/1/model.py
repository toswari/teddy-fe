from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types import Concept
from typing import List


def concept_to_dict(concept: Concept) -> dict:
    return {"id": concept.id, "name": concept.name, "value": concept.value}


class TextClassifierModel(ModelClass):
    def load_model(self):
        pass

    @ModelClass.method
    def predict(self, prompt: str) -> List[Concept]:
        # Example: dummy scores, replace with your model's output
        #  ```json[   {"name": "safe", "value": 0.99999999},   {"name": "suggestive", "value": 0.00000001},   {"name": "drug", "value": 0.00000001},   {"name": "explicit", "value": 0.00000001},   {"name": "gore", "value": 0.00000001} ]```

        scores = {
            "safe": 0.99999999,
            "drug": 1e-08,
            "explicit": 1e-08,
            "gore": 1e-08,
            "suggestive": 1e-08,
        }
        concepts = [Concept(id=k, name=k, value=v) for k, v in scores.items()]
        # return [concept_to_dict(c) for c in concepts] # Commented out because Clarifai expects Concept objects
        return concepts
