FROM traefik:v3.1

RUN mkdir -p /acme && chmod 700 /acme
COPY traefik.yml /etc/traefik/traefik.yml
COPY dynamic_conf.yml /etc/traefik/dynamic_conf.yml
