# Container image of InvenTag (plan 3.4; publishing is the owner's switch).
#
# Build context: the repository root, with the InvenTag wheel of this release
# in dist/ (the release workflow builds it before the PyPI upload):
#
#   docker build -f packaging/docker/Dockerfile \
#     --build-arg PYTHON_DIGEST=sha256:<digest of python:3.13-slim> -t inventag .
#
# The base image is pinned by digest; there is no default, so a build without
# PYTHON_DIGEST fails. Dependencies come only from the hash-pinned lock.
# No version number in this file: the wheel carries it.
ARG PYTHON_DIGEST

FROM python:3.13-slim@${PYTHON_DIGEST} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY requirements-lock.txt /src/requirements-lock.txt
COPY dist/ /src/dist/
RUN python -m venv /opt/inventag \
 && /opt/inventag/bin/pip install --require-hashes --no-deps --only-binary :all: \
      -r /src/requirements-lock.txt \
 && /opt/inventag/bin/pip install --no-deps --no-index /src/dist/inventag_aws-*-py3-none-any.whl \
 && /opt/inventag/bin/pip check

FROM python:3.13-slim@${PYTHON_DIGEST}
COPY --from=build /opt/inventag /opt/inventag
COPY LICENSE /usr/share/doc/inventag/LICENSE
RUN useradd --create-home --uid 10001 --user-group inventag
ENV PATH=/opt/inventag/bin:$PATH PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
WORKDIR /home/inventag
ENTRYPOINT ["inventag"]
CMD ["--help"]
