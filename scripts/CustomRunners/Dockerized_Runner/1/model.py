import json
from typing import Any, Dict, Iterator
from dataclasses import dataclass, asdict
import inspect

"""Baseline Clarifai Runner Model
=================================
Lightweight example provides three endpoints (`predict`, `generate`, `stream`) that:
    - Echo or introspect input
    - Accept raw strings OR JSON (predict / generate)
    - Demonstrate structured chunk streaming (`generate`) and raw text streaming (`stream`)

"""

@dataclass
class MethodInfo:
    name: str
    doc_first_line: str
    parameters: Dict[str, str]


def _collect_method_info(cls) -> Dict[str, MethodInfo]:
    info: Dict[str, MethodInfo] = {}
    for attr_name in dir(cls):
        if attr_name.startswith('_'):
            continue
        attr = getattr(cls, attr_name)
        if callable(attr):
            sig = None
            try:
                sig = inspect.signature(attr)
            except (TypeError, ValueError):
                pass
            params = {}
            if sig:
                for p_name, p in sig.parameters.items():
                    if p_name == 'self':
                        continue
                    params[p_name] = str(p)
            doc = (attr.__doc__ or '').strip().splitlines()
            doc_first = doc[0] if doc else ''
            info[attr_name] = MethodInfo(
                name=attr_name,
                doc_first_line=doc_first,
                parameters=params
            )
    return info


def _parse_prompt(prompt: str) -> Dict[str, Any]:
    """Attempt to parse JSON; if it fails, treat prompt as plain text message.

    Rules:
      - Empty or whitespace -> {}
      - Valid JSON object -> returned as-is
      - Valid JSON (non-object) -> wrapped under {"value": <parsed>}
      - Invalid JSON -> {"message": original_string}
    """
    if not prompt or not prompt.strip():
        return {}
    try:
        parsed = json.loads(prompt)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return {"message": prompt}

# Clarifai hosting boilerplate
from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_utils import Param

class MyModelClass(ModelClass):
    """Baseline model exposing echo + introspection endpoints."""

    def load_model(self):
        """Nothing to load for baseline."""
        pass

    @ModelClass.method
    def predict(self, prompt: str = "", detail: str = Param(default="summary", description="summary or full")) -> str:
        """Echo or introspect a prompt.

        Prompt handling:
          - JSON object -> direct
          - JSON primitive/array -> wrapped as {"value": <parsed>}
          - Invalid JSON / plain text -> {"message": <text>}
        Set action=list_methods to list selected endpoint metadata.
        """
        data = _parse_prompt(prompt)

        action = data.get("action", "echo")
        methods = _collect_method_info(MyModelClass)

        if action == "list_methods":
            payload = {k: asdict(v) for k, v in methods.items() if k in ("predict", "generate", "stream")}
        else:
            payload = {
                "received_keys": list(data.keys()),
                "message": data.get("message"),
                "action": action
            }

        if detail == "full":
            payload["all_methods"] = {k: asdict(v) for k, v in methods.items()}

        return json.dumps({
            "endpoint": "predict",
            "status": "ok",
            "result": payload
        })

    @ModelClass.method
    def generate(
        self,
        prompt: str = "",
        steps: int = Param(default=3, description="number of streamed chunks"),
        minimal: bool = Param(default=True, description="emit minimal fields"),
        include_methods: bool = Param(default=False, description="include method metadata in first chunk")
    ) -> Iterator[str]:
        """Yield small structured chunks.

        If minimal=True (default) each stream chunk contains only:
          {endpoint, index, text, final? (last chunk only)}
        If minimal=False a richer schema is used (similar to former output) and
        optional method metadata can be included when include_methods=True or
        the prompt action == list_methods.
        """
        data = _parse_prompt(prompt)
        message = data.get("message") or data.get("value")
        action = data.get("action")

        methods = None
        if not minimal and (include_methods or action == "list_methods"):
            all_methods = _collect_method_info(MyModelClass)
            methods = {k: asdict(v) for k, v in all_methods.items() if k in ("predict", "generate", "stream")}

        total = max(1, steps)
        for i in range(total):
            if minimal:
                yield json.dumps({
                    "endpoint": "generate",
                    "index": i,
                    "text": message,
                    "final": i == total - 1
                })
            else:
                yield json.dumps({
                    "endpoint": "generate",
                    "status": "stream" if i < total - 1 else "complete",
                    "index": i,
                    "steps": total,
                    "echo": message,
                    "methods": methods if (i == 0 and methods) else None
                })

    @ModelClass.method
    def stream(self, input_iterator: Iterator[str], batch_size: int = Param(default=1, description="unused; kept for SDK compatibility")) -> Iterator[str]:
        """Raw text streaming with optional batching.

        Clarifai's runner may invoke this method with a `batch_size` argument. We implement
        lightweight batching semantics while still emitting one string per *original* input
        so downstream consumers don't need to parse compound payloads:

        Behavior:
          - Read up to `batch_size` items from the iterator at a time.
          - For each item in the batch, yield: "<original_input><optional_space>Stream Hello World <global_index>".
          - Global index increments across batches (matches earlier simple example behavior).

        This keeps the signature compatible with the SDK while demonstrating how one *could*
        respect batch sizing without changing the downstream contract.
        """
        if batch_size < 1:
            batch_size = 1
        global_index = 0
        batch: list[str] = []
        for item in input_iterator:
            batch.append(item)
            if len(batch) >= batch_size:
                for b in batch:
                    # Preserve trailing space if caller provided one (example formatting).
                    if b.endswith(" "):
                        yield f"{b}Stream Hello World {global_index}"
                    else:
                        yield f"{b} Stream Hello World {global_index}"
                    global_index += 1
                batch.clear()
        # Flush remainder
        for b in batch:
            if b.endswith(" "):
                yield f"{b}Stream Hello World {global_index}"
            else:
                yield f"{b} Stream Hello World {global_index}"
            global_index += 1


def test_predict() -> None:
    """Quick test for predict endpoint."""
    model = MyModelClass()
    model.load_model()
    print("Testing predict method:")
    test_input = {"message": "hello world", "action": "list_methods"}
    output = model.predict(json.dumps(test_input), detail="full")
    print(output)

def test_generate() -> None:
    """Quick test for generate endpoint."""
    model = MyModelClass()
    model.load_model()
    print("Testing generate method:")
    test_input = {"message": "stream this"}
    for output in model.generate(json.dumps(test_input), steps=2):
        print(output)

def test_stream() -> None:
    """Quick test for raw text `stream` endpoint (no JSON wrapping)."""
    model = MyModelClass()
    model.load_model()
    print("Testing stream (raw text) method:")
    test_inputs = ["alpha", "beta", "gamma"]
    for output in model.stream(iter(test_inputs), batch_size=2):
        print(output)

def test_error_handling() -> None:
    """Test error handling with invalid JSON input."""
    model = MyModelClass()
    model.load_model()
    print("Testing error handling with invalid JSON:")
    
    # Test with invalid JSON
    invalid_input = "this is not json"
    output = model.predict(invalid_input)
    print(f"Plain String Fallback Response: {output}")
    
    # Test with empty string
    empty_input = ""
    output = model.predict(empty_input)
    print(f"Empty Input Response: {output}")

if __name__ == "__main__":
    test_predict()
    print()
    test_generate()
    print()
    test_stream()
    print()
    test_error_handling()
