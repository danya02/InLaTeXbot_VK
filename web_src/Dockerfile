FROM python:3.9
WORKDIR /
ENTRYPOINT ["gunicorn", "-b", ":8000", "-w", "4", "main:app"]

COPY web_src/requirements.txt /
RUN pip3 install --no-cache -r requirements.txt
COPY web_src/* /
