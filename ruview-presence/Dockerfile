ARG BUILD_FROM
FROM ruvnet/wifi-densepose:latest

# Install WiFi scanning tools needed for CSI_SOURCE=wifi on Linux.
# iw       — modern nl80211-based WiFi scanner (preferred)
# wireless-tools — provides iwlist as fallback
# Handles both Debian/Ubuntu (apt) and Alpine (apk) base images.
RUN (apt-get update && apt-get install -y --no-install-recommends iw wireless-tools \
    && rm -rf /var/lib/apt/lists/*) \
    || apk add --no-cache iw wireless-tools 2>/dev/null \
    || true

# Copy HA sensor package and startup script
COPY ruview_ha_package.yaml /tmp/ruview_ha_package.yaml
COPY run.sh /run.sh
RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]
