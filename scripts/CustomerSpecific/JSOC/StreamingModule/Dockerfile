FROM python:3.13-slim

ENV STREAMLIT_ARGS=""

RUN groupadd -g 999 python && \
  useradd -r -u 999 -g python python
RUN mkdir -p /streamlit/app && chown python:python /streamlit/app
USER root
RUN chown 999:999 /streamlit/app
RUN apt-get remove openssl -y
RUN apt update && apt install -y git ffmpeg libsm6 libxext6
USER python

COPY --chown=999:999 . /streamlit/app/

# setup venv
WORKDIR /streamlit/app
RUN python -m venv /streamlit/app/venv
ENV PATH="/streamlit/app/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501
ENTRYPOINT streamlit run app.py ${STREAMLIT_ARGS}