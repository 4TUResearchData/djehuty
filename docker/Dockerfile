FROM debian:bookworm-slim
LABEL authors="Nikhef"

# build with: docker image build -t djehuty:latest .
# start with: docker container run --rm -ti -v ../etc/djehuty/djehuty-example-config.xml:/config.xml:Z djehuty:latest /bin/djehuty web -c /config.xml

RUN apt-get update && apt-get install -y python3 python3-venv git
RUN rm -rf /var/lib/dpkg/info/*.list /var/lib/apt/lists/*
RUN useradd -mg users -d /opt/djehuty -u 7001 djehuty
RUN mkdir -p /data && chown -R djehuty: /data

RUN echo '#!/bin/sh\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/djehuty $@' > /usr/bin/djehuty && chmod +x /usr/bin/djehuty

USER djehuty

RUN git clone --depth 1 https://github.com/4TUResearchData/djehuty.git /opt/djehuty/djehuty
RUN VERSION=$(git -C /opt/djehuty/djehuty rev-parse --short HEAD); sed -e "s/@VERSION@/0.0.0+${VERSION}/g" /opt/djehuty/djehuty/pyproject.toml.in > /opt/djehuty/djehuty/pyproject.toml

RUN python3 -m venv /opt/djehuty/virtual-env
RUN . /opt/djehuty/virtual-env/bin/activate && \
    pip install -r /opt/djehuty/djehuty/requirements.txt python3-saml && \
    pip install --editable /opt/djehuty/djehuty

CMD ["/bin/bash"]
