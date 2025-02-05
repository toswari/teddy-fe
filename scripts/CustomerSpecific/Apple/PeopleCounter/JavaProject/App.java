package com.example.videoprocessor;

import java.io.File;
import java.net.URL;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import com.amazonaws.auth.AWSStaticCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.GeneratePresignedUrlRequest;
import com.clarifai.channel.ClarifaiChannel;
import com.clarifai.credentials.ClarifaiCallCredentials;
import com.clarifai.grpc.api.Concept;
import com.clarifai.grpc.api.Data;
import com.clarifai.grpc.api.Frame;
import com.clarifai.grpc.api.Input;
import com.clarifai.grpc.api.Output;
import com.clarifai.grpc.api.PostWorkflowResultsRequest;
import com.clarifai.grpc.api.PostWorkflowResultsResponse;
import com.clarifai.grpc.api.Region;
import com.clarifai.grpc.api.UserAppIDSet;
import com.clarifai.grpc.api.V2Grpc;
import com.clarifai.grpc.api.Video;
import com.clarifai.grpc.api.WorkflowResult;
import com.clarifai.grpc.api.status.StatusCode;

import net.bramp.ffmpeg.FFmpeg;
import net.bramp.ffmpeg.FFmpegExecutor;
import net.bramp.ffmpeg.builder.FFmpegBuilder;

public class App {

    static final String AWS_ACCESS_KEY = "Key Here";
    static final String AWS_SECRET_KEY = "Secret Here";
    static final String BUCKET_NAME = "clarifai-prod-apple-project";
    static final String USER_ID = "nclp9tndqh0r";
    static final String PAT = "PAT_HERE";
    static final String APP_ID = "apple-products";
    static final String WORKFLOW_ID = "GeneralTag-and-PeopleCount";
    static final String FFMPEG_PATH = "C:/Program Files/ffmpeg/bin/ffmpeg.exe";

    public static void main(String[] args) throws Exception {
        String videoFilePath = "D://videos/test.mp4";
        List<String> videoParts = splitVideo(videoFilePath);

        for (String videoPart : videoParts) {
            PresignedUrls urls = generatePresignedUrls(videoPart); 
            uploadVideoToS3(videoPart, urls.getUploadUrl()); 
            processWithClarifai(urls.getDownloadUrl());
            new File(videoPart).delete();
        }
    }

    public static List<String> splitVideo(String videoFilePath) throws Exception {
        FFmpeg ffmpeg = new FFmpeg(FFMPEG_PATH);
        FFmpegExecutor executor = new FFmpegExecutor(ffmpeg);

        long totalDuration = getVideoDurationInSeconds(videoFilePath);
        long maxPartDuration = 90 * 60; // 90 minutes per part
        int parts = (int) Math.ceil((double) totalDuration / maxPartDuration);

        List<String> videoParts = new ArrayList<>();
        for (int i = 0; i < parts; i++) {
            String outputFilePath = "video_part_" + i + ".mp4";
            FFmpegBuilder builder = new FFmpegBuilder()
                .setInput(videoFilePath)
                .addOutput(outputFilePath)
                .setStartOffset(i * maxPartDuration, TimeUnit.SECONDS)
                .setDuration(maxPartDuration, TimeUnit.SECONDS)
                .done();
            executor.createJob(builder).run();
            videoParts.add(outputFilePath);
        }
        return videoParts;
    }

    public static long getVideoDurationInSeconds(String videoFilePath) throws Exception {
        return 5400; // Placeholder for 1.5 hours; replace with actual duration logic
    }

    public static class PresignedUrls {
        private final String uploadUrl;
        private final String downloadUrl;

        public PresignedUrls(String uploadUrl, String downloadUrl) {
            this.uploadUrl = uploadUrl;
            this.downloadUrl = downloadUrl;
        }

        public String getUploadUrl() {
            return uploadUrl;
        }

        public String getDownloadUrl() {
            return downloadUrl;
        }
    }

    public static PresignedUrls generatePresignedUrls(String videoPartPath) {
        BasicAWSCredentials awsCreds = new BasicAWSCredentials(AWS_ACCESS_KEY, AWS_SECRET_KEY);
        AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
                .withRegion("us-east-1")
                .withCredentials(new AWSStaticCredentialsProvider(awsCreds))
                .build();

        String fileName = Paths.get(videoPartPath).getFileName().toString();

        // Generate PUT URL (for upload)
        GeneratePresignedUrlRequest putUrlRequest = new GeneratePresignedUrlRequest(BUCKET_NAME, fileName)
                .withMethod(com.amazonaws.HttpMethod.PUT)
                .withExpiration(new java.util.Date(System.currentTimeMillis() + 3600 * 1000));  // URL valid for 1 hour
        URL putPresignedUrl = s3Client.generatePresignedUrl(putUrlRequest);

        // Generate GET URL (for download)
        GeneratePresignedUrlRequest getUrlRequest = new GeneratePresignedUrlRequest(BUCKET_NAME, fileName)
                .withMethod(com.amazonaws.HttpMethod.GET)
                .withExpiration(new java.util.Date(System.currentTimeMillis() + 3600 * 1000));  // URL valid for 1 hour
        URL getPresignedUrl = s3Client.generatePresignedUrl(getUrlRequest);

        // Return both URLs
        return new PresignedUrls(putPresignedUrl.toString(), getPresignedUrl.toString());
    }

    public static void uploadVideoToS3(String videoPartPath, String presignedUrl) {
        File file = new File(videoPartPath);
        try {
            java.net.HttpURLConnection connection = (java.net.HttpURLConnection) new URL(presignedUrl).openConnection();
            connection.setRequestMethod("PUT");
            connection.setDoOutput(true);
            try (java.io.OutputStream outputStream = connection.getOutputStream()) {
                java.nio.file.Files.copy(file.toPath(), outputStream);
            }
            int responseCode = connection.getResponseCode();
            if (responseCode != 200) {
                throw new RuntimeException("Failed to upload video part. HTTP response code: " + responseCode);
            }
        } catch (java.io.IOException e) {
            throw new RuntimeException("Error uploading video to S3", e);
        }
    }

    public static void processWithClarifai(String videoUrl) {
        System.out.println("Processing video with Clarifai: " + videoUrl);
        V2Grpc.V2BlockingStub stub = V2Grpc.newBlockingStub(ClarifaiChannel.INSTANCE.getGrpcChannel())
                .withCallCredentials(new ClarifaiCallCredentials(PAT));
        
        PostWorkflowResultsResponse response = stub.postWorkflowResults(
                PostWorkflowResultsRequest.newBuilder()
                        .setUserAppId(UserAppIDSet.newBuilder().setUserId(USER_ID).setAppId(APP_ID))
                        .setWorkflowId(WORKFLOW_ID)
                        .addInputs(Input.newBuilder().setData(Data.newBuilder().setVideo(Video.newBuilder().setUrl(videoUrl))))
                        .build()
        );
    
        if (response.getStatus().getCode() != StatusCode.SUCCESS) {
            throw new RuntimeException("Clarifai API call failed: " + response.getStatus().getDescription());
        } else {
            System.out.println("Clarifai processing completed successfully");
        }
        int maxPeoplePerFrame = 0;
        double totalPeopleConfidence = 0;
        int totalPeopleDetections = 0;
        Map<String, Double> otherObjects = new HashMap<>();
        for (WorkflowResult result : response.getResultsList()) {
            for (Output output : result.getOutputsList()) {
                if (output.getData().getFramesList() != null && !output.getData().getFramesList().isEmpty()) {
                    for (Frame frame : output.getData().getFramesList()) {
                        int peopleInFrame = 0;
    
                        for (Region region : frame.getData().getRegionsList()) {
                            for (Concept concept : region.getData().getConceptsList()) {
                                if (concept.getName().equals("person")) {
                                    peopleInFrame++;
                                    totalPeopleConfidence += concept.getValue();
                                    totalPeopleDetections++;
                                } else {
                                    otherObjects.put(
                                        concept.getName(),
                                        otherObjects.getOrDefault(concept.getName(), 0.0) + concept.getValue()
                                    );
                                    System.out.println("Other object: " + concept.getName() + " with confidence: " + concept.getValue());
                                }
                            }
                        }
                        if (peopleInFrame > maxPeoplePerFrame) {
                            maxPeoplePerFrame = peopleInFrame;
                        }
                    }
                } else if (output.getData().getConceptsList() != null && !output.getData().getConceptsList().isEmpty()) {
                    for (Concept concept : output.getData().getConceptsList()) {
                        System.out.println(concept.getName() + ": " + concept.getValue());
                    }
                } else {
                    System.out.println("No frames or concepts found in output.");
                }
            }
        }
    
        double averagePeopleConfidence = (totalPeopleDetections > 0) ? (totalPeopleConfidence / totalPeopleDetections) : 0;
        System.out.println("Max number of people in a frame: " + maxPeoplePerFrame);
        System.out.println("Average confidence for people predictions: " + averagePeopleConfidence);
        System.out.println("Other objects detected:");
        for (Map.Entry<String, Double> entry : otherObjects.entrySet()) {
            System.out.println(entry.getKey() + ": " + entry.getValue());
        }
    }
    
    
    
}
