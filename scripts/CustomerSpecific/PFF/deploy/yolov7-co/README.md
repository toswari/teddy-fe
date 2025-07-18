# Deploying YoloV7 to Clairfai CO with ONNX
1. `[uv] pip install clarifai`
1. Ensure the config.yaml is correct
  1. Set the model name, user id, app id
  2. Ensure the concepts list matches the order of model output
     **and that the concept id is the id from the app**
     - **WARN: IF YOU DON'T DO THIS, NEW CONCEPTS WILL BE CREATED IN THE APP AND YOU'LL BE *VERY* CONFUSED**
2. The following, *note the --skip_dockerfile*!
    ```shell
    # Export
    python export.py --weights $WEIGHTS_PATH --grid --end2end --simplify --img-size 640 640 --max-wh 640 --conf-thres 0.3

    # Copy weights
    cp $(dirname $WEIGHTS_PATH)/best.onnx 1/model.onnx

    # Test
    clarifai model run-locally --skip_dockerfile -p 8000 --mode container $(pwd)

    CLARIFAI_API_BASE=localhost:8000 example_inference.py --image $IMAGE_PATH --test-latency

    # Upload
    clarifai model upload --skip_dockerfile $(pwd)
    ```
3. If you need class agnostic NMS, you need to modify `models.experimental` to zero out displacement (L184)