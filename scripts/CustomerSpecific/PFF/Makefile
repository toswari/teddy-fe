build:
	@echo "Building the project..."
	uv build

build-container:
	-docker build -t $(TAG) $(CONTEXT) || \
	nerdctl build -t $(TAG) $(CONTEXT) || \
	lima nerdctl build -t $(TAG) $(CONTEXT)

deploy-yolo-preflight:
	@echo "yolov7 preflight"
	uv build --sdist -o deploy/yolov7-co/dist
	@echo "Trying docker build..."
	$(MAKE) build-container TAG=yolov7:preflight CONTEXT=deploy/yolov7-co

deploy-yolo:
	@echo "Deploying yolov7..."
	uv build --sdist -o deploy/yolov7-co/dist
	clarifai model upload --skip_dockerfile deploy/yolov7-co/

deploy-video-detect-track-preflight:
	@echo "Deploying video detect..."
	uv build --sdist -o deploy/video-detect-track/dist
	$(MAKE) build-container TAG=video-detect-track:preflight CONTEXT=deploy/video-detect-track/

deploy-video-detect-track:
	@echo "Deploying video detect track..."
	uv build --sdist -o deploy/video-detect-track/dist
	cp -r models/ deploy/video-detect-track/1/
	clarifai model upload --skip_dockerfile deploy/video-detect-track/

reid:
	@echo "Training ReID model..."
	python scripts/train_reid.py \
		--databatch-folder $(DB_FOLDER) \
		--gt-folder $(GT_FOLDER) \
		--output models \
		--tag reid.skl \
		--min-frames 2 \
		--max-frames 30 \
		--skip-frames 2

clean:
	@echo "Cleaning up..."
	rm -rf dist/
	rm -rf deploy/yolov7-co/dist/
	rm -rf deploy/video-detect-track/dist/
	rm -rf deploy/video-detect-track/1/*.onnx
	rm -rf deploy/video-detect-track/1/*.skl
