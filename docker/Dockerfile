FROM debian:bookworm-slim
LABEL authors="Nikhef, 4TU.ResearchData"
ARG PURPOSE="release"
ARG VERSION="0.0.0"

# Build a self-updating (development) container:
# docker image build --build-arg="PURPOSE=development" -t djehuty:devel -f docker/Dockerfile .
#
# Or a non-self-updating (release) container:
# docker image build -t djehuty:latest -f docker/Dockerfile .
#
# start with: docker container run --rm -ti -v ../etc/djehuty/djehuty-example-config.xml:/config.xml:Z djehuty:latest /bin/djehuty web -c /config.xml

RUN apt-get update \
    && apt-get install -y build-essential git libxmlsec1-dev pkg-config python3 python3-dev python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/dpkg/info/*.list /var/lib/apt/lists/* \
    && useradd -mg users -d /opt/djehuty -u 7001 djehuty \
    && mkdir -p /data && chown -R djehuty: /data \
    &&  echo '#!/bin/sh\n/usr/bin/git -C /opt/djehuty/djehuty pull\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/pip install --editable /opt/djehuty/djehuty\n' > /usr/bin/update-djehuty \
    && chmod +x /usr/bin/update-djehuty \
    && UPDATE_COMMAND=""; if [ "$PURPOSE" = "development" ]; then UPDATE_COMMAND="/usr/bin/update-djehuty"; fi; echo '#!/bin/sh\n'${UPDATE_COMMAND}'\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/djehuty $@' > /usr/bin/djehuty && chmod +x /usr/bin/djehuty

USER djehuty

COPY --chown=djehuty:users . /opt/djehuty/djehuty/

WORKDIR /opt/djehuty/djehuty

RUN python3 -m venv /opt/djehuty/virtual-env \
    && . /opt/djehuty/virtual-env/bin/activate \
    && pip install --no-binary lxml,xmlsec python3-saml \
    && if [ -f docker/requirements.lock ]; then \
         pip install -r docker/requirements.lock; \
         pip install --no-deps --editable .; \
       else \
         pip install --editable .; \
       fi

CMD ["/bin/bash"]
