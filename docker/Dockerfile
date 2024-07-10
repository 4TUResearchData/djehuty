FROM debian:bookworm-slim
LABEL authors="Nikhef, 4TU.ResearchData"
ARG PURPOSE="release"

# Build a self-updating (development) container:
# docker image build --build-arg="PURPOSE=development" -t djehuty:devel .
#
# Or a non-self-updating (release) container:
# docker image build -t djehuty:latest .
#
# start with: docker container run --rm -ti -v ../etc/djehuty/djehuty-example-config.xml:/config.xml:Z djehuty:latest /bin/djehuty web -c /config.xml

RUN apt-get update && apt-get install -y python3 python3-venv git
RUN rm -rf /var/lib/dpkg/info/*.list /var/lib/apt/lists/*
RUN useradd -mg users -d /opt/djehuty -u 7001 djehuty
RUN mkdir -p /data && chown -R djehuty: /data

# Perform 'git pull', then update the djehuty package installation so the version number matches.
RUN echo '#!/bin/sh\n/usr/bin/git -C /opt/djehuty/djehuty pull\nVERSION=$(git -C /opt/djehuty/djehuty rev-parse --short HEAD); sed -e "s/@VERSION@/0.0.0+${VERSION}/g" /opt/djehuty/djehuty/pyproject.toml.in > /opt/djehuty/djehuty/pyproject.toml\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/pip install --editable /opt/djehuty/djehuty\n' > /usr/bin/update-djehuty && chmod +x /usr/bin/update-djehuty

RUN UPDATE_COMMAND=""; if [ "$PURPOSE" = "development" ]; then UPDATE_COMMAND="/usr/bin/update-djehuty"; fi; echo '#!/bin/sh\n'${UPDATE_COMMAND}'\nVIRTUAL_ENV=/opt/djehuty/virtual-env\n/opt/djehuty/virtual-env/bin/djehuty $@' > /usr/bin/djehuty && chmod +x /usr/bin/djehuty

USER djehuty

RUN git clone --depth 1 https://github.com/4TUResearchData/djehuty.git /opt/djehuty/djehuty
RUN VERSION=$(git -C /opt/djehuty/djehuty rev-parse --short HEAD); sed -e "s/@VERSION@/0.0.0+${VERSION}/g" /opt/djehuty/djehuty/pyproject.toml.in > /opt/djehuty/djehuty/pyproject.toml

RUN python3 -m venv /opt/djehuty/virtual-env
RUN . /opt/djehuty/virtual-env/bin/activate && \
    pip install -r /opt/djehuty/djehuty/requirements.txt python3-saml && \
    pip install --editable /opt/djehuty/djehuty

CMD ["/bin/bash"]
