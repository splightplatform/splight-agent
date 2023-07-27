FROM python:3.11

ENV PYTHONUNBUFFERED=1

RUN apt update --fix-missing

RUN pip install --upgrade pip && pip install poetry==1.5.1

# Copy only requirements to cache them in docker layer
WORKDIR /code
COPY poetry.lock pyproject.toml /code/

# Install poetry dependencies
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-root

# INSTALL AWS CLI
RUN pip install awscli

# Install docker
RUN apt-get update
RUN apt-get install ca-certificates curl gnupg -y
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN chmod a+r /etc/apt/keyrings/docker.gpg
RUN echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update
RUN apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

COPY . /code