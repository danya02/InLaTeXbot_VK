FROM python:3.9

COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/tex* /usr/share/
RUN rm -rf /usr/share/texmf/doc
COPY --from=danya02/raspberry-pi-texlive-full:latest /etc/texmf /etc/
COPY --from=danya02/raspberry-pi-texlive-full:latest /var/lib/tex* /var/lib/
COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/latex* /usr/share
COPY --from=danya02/raspberry-pi-texlive-full:latest /usr/share/fonts* /usr/share/


ADD renderer_src/requirements.txt /
RUN pip3 install -r requirements.txt
ADD renderer_src/* /

ENTRYPOINT celery -A latex_celery_tasks:cel worker --loglevel INFO 
