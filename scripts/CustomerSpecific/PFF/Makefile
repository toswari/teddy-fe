.PHONY: build deploy install clean

build:
	@echo "Building the project..."
	uv build

deploy-yolo-preflight:
	@echo "yolov7 preflight"
    # Add deployment commands here, e.g.:
    # ./deploy.sh --profile $(PROFILE)
	uv build --sdist -o deploy/yolov7-co/dist
	lima nerdctl build -t yolov7:preflight deploy/yolov7-co

deploy-yolo:
	@echo "Deploying yolov7..."
	uv build --sdist -o deploy/yolov7-co/dist
	clarifai model upload --skip_dockerfile deploy/yolov7-co/

deploy-video-detect-track-preflight:
	@echo "Deploying video detect..."
	uv build --sdist -o deploy/video-detect-track/dist
	lima nerdctl build -t video-detect-track:preflight deploy/video-detect-track/

deploy-video-detect-track:
	@echo "Deploying video detect track..."
	uv build --sdist -o deploy/video-detect-track/dist
	clarifai model upload --skip_dockerfile deploy/video-detect-track/

clean:
	@echo "Cleaning up..."
	rm -rf dist/
	rm -rf deploy/yolov7-co/dist/
	rm -rf deploy/video-detect-track/dist/
