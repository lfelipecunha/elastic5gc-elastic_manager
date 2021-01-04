FROM python

WORKDIR /elastic_manager

ADD requirements.txt .

RUN pip install -r requirements.txt

ADD src .

VOLUME [ "/elastic_manager/config" ]