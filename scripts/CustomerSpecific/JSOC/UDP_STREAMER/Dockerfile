FROM jrottenberg/ffmpeg:5-ubuntu

WORKDIR /app
COPY video.mp4 /app/video.mp4

ENTRYPOINT []
CMD ["ffmpeg", "-stream_loop", "-1", "-re", "-i", "video.mp4", "-f", "mpegts", "udp://224.0.0.1:1234?pkt_size=1316"]
