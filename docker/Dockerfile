FROM debian:bookworm-slim
LABEL authors="Nikhef"

# build with: docker image build -t djehuty:latest .
# start with: docker container run --rm -ti -v $PWD/djehuty-example-config.xml:/djehuty-example-config.xml djehuty:latest

ENV DJEHUTY_VERSION 0.0.1

RUN apt-get update && \
    apt-get install -y \
      python3 \
      python3-dev \
      pkg-config \
      libxml2-dev \
      libxmlsec1-dev \
      libxmlsec1-openssl \
      python3-pip \
      python3-venv \
      build-essential \
      git \
    && \
    rm -rf /var/lib/dpkg/info/*.list /var/lib/apt/lists/* && \
    useradd -mg users -u 7001 djehuty && \
    mkdir /data && chown -R djehuty: /data

USER djehuty
WORKDIR /home/djehuty

RUN python3 -m venv djehuty-env && . djehuty-env/bin/activate && \
    git clone --depth 1 https://github.com/4TUResearchData/djehuty.git && \
    cd djehuty && pip install python3-saml && \
    pip install -r requirements.txt && \
    sed -e "s/@VERSION@/${DJEHUTY_VERSION}/g" pyproject.toml.in > pyproject.toml && \
    pip install --editable .

COPY scripts/ .

CMD ["/bin/bash"]


