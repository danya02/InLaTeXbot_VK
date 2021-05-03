FROM python:3.9
WORKDIR /

COPY web_src/requirements.txt /
RUN pip3 install --no-cache -r requirements.txt
COPY web_src/* /
RUN mkdir /templates
COPY web_src/templates/ /templates/
ENTRYPOINT ["gunicorn", "-b", ":8000", "--access-logfile", "-", "--capture-output", "-w", "4", "main:app"]
