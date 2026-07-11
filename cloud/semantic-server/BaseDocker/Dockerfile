FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime
# install nginx, reuse
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx git libgl1 libglib2.0-dev && \
    rm -rf /var/lib/apt/lists/*
# install python requirements
COPY requirements.txt /opt/nvi_server/
WORKDIR /opt/nvi_server
RUN /opt/conda/bin/python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    /opt/conda/bin/conda clean -ya && \
    /opt/conda/bin/python -m pip cache purge && \
    rm -rf requirements.txt
