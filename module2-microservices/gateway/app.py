"""API Gateway - the single entry point for clients. Port 5000 (env GATEWAY_PORT).

It owns NO data. It forwards /api/... requests to the responsible service.
Feature 2 (authentication) and Feature 3 (audit logging) are cross-cutting
concerns; the domain services must stay unaware of them.
"""
import os

import requests
from flask import Flask, Response, jsonify, request

DEVICE_URL = os.environ.get("DEVICE_URL", "http://127.0.0.1:5001")
READING_URL = os.environ.get("READING_URL", "http://127.0.0.1:5002")
ALERT_URL = os.environ.get("ALERT_URL", "http://127.0.0.1:5003")
app = Flask(__name__)


def forward(base_url: str, path: str) -> Response:
    """Relay the current request to <base_url><path> and return the response."""
    try:
        upstream = requests.request(
            method=request.method,
            url=f"{base_url}{path}",
            params=request.args,
            json=request.get_json(silent=True),
            timeout=5,
        )
    except requests.RequestException as exc:
        return jsonify(error="upstream service unavailable", detail=str(exc)), 503
    return Response(upstream.content, status=upstream.status_code,
                    content_type=upstream.headers.get("Content-Type", "application/json"))


@app.get("/health")
def health():
    status = {}
    for name, url in (("device", DEVICE_URL), ("reading", READING_URL), ("alert", ALERT_URL)):
        try:
            status[name] = requests.get(f"{url}/health", timeout=1).json().get("status")
        except requests.RequestException:
            status[name] = "down"
    return jsonify(service="gateway", upstream=status)


# ---- devices -----------------------------------------------------------
@app.route("/api/devices", methods=["GET", "POST"])
def devices():
    return forward(DEVICE_URL, "/devices")


@app.get("/api/devices/<int:device_id>")
def device(device_id):
    return forward(DEVICE_URL, f"/devices/{device_id}")


# (Feature 1): DELETE /api/devices/<id>
@app.delete("/api/devices/<int:device_id>")
def route_delete_devices_request(device_id): #flask will pass the device_id from the url to this function
    # readings db holds a reference to device_id, i.e. readings depends on device
    # so delete readings first before deleting devices

    # DELETE READINGS:
    try:
        #create a delete request to the readings_service with the device_id parameter
        readings_response = requests.delete(
                                url = f"{READING_URL}/readings",
                                params = {"device_id" : device_id},
                                timeout = 5
                            )
    except requests.RequestException as request_exception:
        return jsonify(
                error = "Reading service unavailable. Device readings could not be deleted",
                detail = str(request_exception)
            ), 503
    
    # if the reading service responded with any error:
    if readings_response.status_code != 200:
        return jsonify (
                error = "Reading service failed. Device readings could not be deleted.",
                upstream_status = readings_response.status_code
            ), 502
    
    # DELETE THE DEVICE
    try:
        device_response = requests.delete(
                                url = f"{DEVICE_URL}/devices/{device_id}",
                                timeout = 5
                            )
    except requests.RequestException as request_exception:
        return jsonify(
                error = "Device service unavailable. Readings were deleted but device still exists.",
                detail = str(request_exception)
            ), 503

    #if the device service responded with any error:
    if device_response.status_code == 404:
        return jsonify(error = "Device not found."), 404
    
    elif device_response.status_code != 200:
        return jsonify(
                error = "Device service failed. Readings are deleted but device still exists.",
                upstream_status = device_response.status_code
            ), 502

    #if both readings and device have been deleted successfully:
    return jsonify(
            deleted = device_id,
            num_readings_deleted = readings_response.json().get("deleted")
        ), 200    

# ---- readings ----------------------------------------------------------
@app.route("/api/readings", methods=["GET", "POST"])
def readings():
    return forward(READING_URL, "/readings")


# ---- alerts ------------------------------------------------------------
@app.get("/api/alerts")
def alerts():
    return forward(ALERT_URL, "/alerts")


# TODO (Feature 2): /api/auth/register, /api/auth/login and a check that every
#                   other /api/* request carries a valid token.
# TODO (Feature 3): record every /api/* action in an audit service; GET /api/audit.


@app.errorhandler(404)
def not_found(_exc):
    return jsonify(error="no such route"), 404


@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("unhandled error")
    return jsonify(error="internal error", detail=str(exc)), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("GATEWAY_PORT", 5000)))
