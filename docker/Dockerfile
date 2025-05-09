FROM debian:bookworm-slim
LABEL authors="Nikhef, 4TU.ResearchData"
ARG PURPOSE="release"
ARG BRANCH="main"
ARG VERSION="0.0.0"

# Build a self-updating (development) container:
# docker image build --build-arg="PURPOSE=development" -t djehuty:devel .
#
# Or a non-self-updating (release) container:
# docker image build -t djehuty:latest .
#
# start with: docker container run --rm -ti -v ../etc/djehuty/djehuty-example-config.xml:/config.xml:Z djehuty:latest /bin/djehuty web -c /config.xml

RUN apt-get update \
    && apt-get install -y build-essential git libxmlsec1-dev pkg-config python3 python3-dev python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/dpkg/info/*.list /var/lib/apt/lists/* \
    && useradd -mg users -d /opt/djehuty -u 7001 djehuty \
    && mkdir -p /data && chown -R djehuty: /data \
    &&  echo '#!/bin/sh\n/usr/bin/git -C /opt/djehuty/djehuty pull\nGIT_VERSION=$(git -C /opt/djehuty/djehuty rev-parse --short HEAD) sed -e "s/@VERSION@/${VERSION}+${GIT_VERSION}/g" /opt/djehuty/djehuty/pyproject.toml.in > /opt/djehuty/djehuty/pyproject.toml\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/pip install --editable /opt/djehuty/djehuty\n' > /usr/bin/update-djehuty \
    && chmod +x /usr/bin/update-djehuty \
    && UPDATE_COMMAND=""; if [ "$PURPOSE" = "development" ]; then UPDATE_COMMAND="/usr/bin/update-djehuty"; fi; echo '#!/bin/sh\n'${UPDATE_COMMAND}'\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/djehuty $@' > /usr/bin/djehuty && chmod +x /usr/bin/djehuty

USER djehuty

RUN git clone --branch "$BRANCH" --depth 1 https://github.com/4TUResearchData/djehuty.git /opt/djehuty/djehuty \
    && GIT_VERSION=$(git -C /opt/djehuty/djehuty rev-parse --short HEAD); sed -e "s/@VERSION@/${VERSION}+${GIT_VERSION}/g" /opt/djehuty/djehuty/pyproject.toml.in > /opt/djehuty/djehuty/pyproject.toml \
    && python3 -m venv /opt/djehuty/virtual-env \
    && . /opt/djehuty/virtual-env/bin/activate \
    && pip install -r /opt/djehuty/djehuty/requirements.txt --no-binary lxml python3-saml \
    && pip install --editable /opt/djehuty/djehuty

CMD ["/bin/bash"]
