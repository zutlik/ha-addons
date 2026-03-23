ARG BUILD_FROM
FROM ruvnet/wifi-densepose:latest

# Copy HA sensor package and startup script
COPY ruview_ha_package.yaml /tmp/ruview_ha_package.yaml
COPY run.sh /run.sh
RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]
