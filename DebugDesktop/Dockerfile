FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y software-properties-common wget \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update

RUN apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-distutils \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://bootstrap.pypa.io/get-pip.py \
    && python3.11 get-pip.py \
    && rm get-pip.py

RUN wget https://dl.min.io/client/mc/release/linux-amd64/mc \
    && chmod +x mc \
    && mv mc /usr/local/bin/

RUN python3.11 -m pip install --no-cache-dir \
    clarifai \
    clarifai-grpc

RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    tomcat9 \
    default-jdk \
    build-essential \
    libcairo2-dev \
    libjpeg-turbo8-dev \
    libpng-dev \
    libtool-bin \
    libossp-uuid-dev \
    libavcodec-dev \
    libavutil-dev \
    libswscale-dev \
    freerdp2-dev \
    libpango1.0-dev \
    libssh2-1-dev \
    libvncserver-dev \
    libtelnet-dev \
    libssl-dev \
    libvorbis-dev \
    libwebp-dev \
    xfce4 \
    xfce4-terminal \
    tigervnc-standalone-server \
    tigervnc-common \
    dbus-x11 \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

ENV GUAC_VERSION=1.4.0

RUN wget https://archive.apache.org/dist/guacamole/${GUAC_VERSION}/source/guacamole-server-${GUAC_VERSION}.tar.gz \
    && tar -xzf guacamole-server-${GUAC_VERSION}.tar.gz \
    && cd guacamole-server-${GUAC_VERSION} \
    && ./configure --with-init-dir=/etc/init.d \
    && make \
    && make install \
    && ldconfig \
    && cd .. \
    && rm -rf guacamole-server-${GUAC_VERSION}*

RUN mkdir -p /etc/guacamole \
    && wget https://archive.apache.org/dist/guacamole/${GUAC_VERSION}/binary/guacamole-${GUAC_VERSION}.war \
    && mv guacamole-${GUAC_VERSION}.war /var/lib/tomcat9/webapps/guacamole.war

RUN mkdir -p /etc/guacamole/extensions /etc/guacamole/lib
ENV GUACAMOLE_HOME=/etc/guacamole

RUN useradd -m -s /bin/bash vnc_user \
    && echo "vnc_user:vncpass123" | chpasswd \
    && echo "vnc_user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/vnc_user/.vnc
COPY xstartup /home/vnc_user/.vnc/xstartup
RUN chmod +x /home/vnc_user/.vnc/xstartup \
    && chown -R vnc_user:vnc_user /home/vnc_user/.vnc \
    && echo "vncpass123" | vncpasswd -f > /home/vnc_user/.vnc/passwd \
    && chmod 600 /home/vnc_user/.vnc/passwd \
    && chown vnc_user:vnc_user /home/vnc_user/.vnc/passwd

COPY guacamole.properties /etc/guacamole/
COPY user-mapping.xml /etc/guacamole/
COPY xfce-stripes.png /usr/share/backgrounds/xfce/

RUN mkdir -p /home/vnc_user/.config/xfce4/xfconf/xfce-perchannel-xml/
RUN echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<channel name="xfce4-desktop" version="1.0">\n\
  <property name="backdrop" type="empty">\n\
    <property name="screen0" type="empty">\n\
      <property name="monitor0" type="empty">\n\
        <property name="workspace0" type="empty">\n\
          <property name="color-style" type="int" value="0"/>\n\
          <property name="image-style" type="int" value="5"/>\n\
          <property name="last-image" type="string" value="/usr/share/backgrounds/xfce/xfce-stripes.png"/>\n\
        </property>\n\
      </property>\n\
    </property>\n\
  </property>\n\
</channel>' > /home/vnc_user/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml

RUN chown -R vnc_user:vnc_user /home/vnc_user/.config

RUN ln -s /etc/guacamole /usr/share/tomcat9/.guacamole

RUN mkdir -p /var/lib/tomcat9/temp \
    && chown -R tomcat:tomcat /var/lib/tomcat9 \
    && chown -R tomcat:tomcat /etc/guacamole

EXPOSE 8080 5901

RUN echo '#!/bin/bash\n\
\n\
echo "Starting guacd..."\n\
/usr/local/sbin/guacd -b 0.0.0.0 -l 4822 -f &\n\
GUACD_PID=$!\n\
\n\
echo "Waiting for guacd to start..."\n\
sleep 5\n\
\n\
# Verify guacd is running\n\
if ! ps -p $GUACD_PID > /dev/null; then\n\
    echo "guacd failed to start!"\n\
    exit 1\n\
fi\n\
\n\
echo "Starting VNC server..."\n\
su - vnc_user -c "vncserver :1 -geometry 1920x1080 -depth 24 -localhost no"\n\
\n\
echo "Starting Tomcat..."\n\
catalina.sh run' > /start.sh && \
chmod +x /start.sh

RUN mkdir -p /var/run/guacd && \
    chmod 755 /var/run/guacd

ENV CATALINA_HOME=/usr/share/tomcat9
ENV CATALINA_BASE=/var/lib/tomcat9
ENV PATH $CATALINA_HOME/bin:$PATH

CMD ["/start.sh"]
