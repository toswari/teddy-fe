from clarifai_token_estimator.clarifai_client import ClarifaiOpenAIClient


def test_extract_text_from_nested_output_blocks() -> None:
    content = [
        {
            "type": "output_text",
            "text": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": " world"},
            ],
        },
        {"type": "output_text", "text": [{"type": "text", "text": "!"}]},
    ]

    assert ClarifaiOpenAIClient._extract_text_from_content(content) == "Hello world!"


def test_extract_text_ignores_image_blocks() -> None:
    content = [
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,abc"},
        },
        {"type": "text", "text": "The description"},
    ]

    assert ClarifaiOpenAIClient._extract_text_from_content(content) == "The description"


def test_extract_text_from_content_container() -> None:
    content = {
        "content": [
            {
                "type": "output_text",
                "text": [
                    {"type": "text", "text": "Layered"},
                    {"type": "text", "text": " parsing"},
                ],
            }
        ]
    }

    assert ClarifaiOpenAIClient._extract_text_from_content(content) == "Layered parsing"
