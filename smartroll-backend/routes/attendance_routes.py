from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, Student, Session, AttendanceLog, ApprovedSubnet
from routes.auth_routes import require_admin_key

attendance_bp = Blueprint("attendance_bp", __name__, url_prefix="/attendance")

# -------------------------
# Helper — Check if IP is allowed
# -------------------------
def ip_in_approved_subnet(client_ip: str) -> bool:
    """
    Check if the client_ip begins with any approved subnet prefix.
    Example: if client_ip="192.168.0.42" and prefix="192.168.0."
    """
    if not client_ip:
        return False

    subnets = ApprovedSubnet.query.all()

    for subnet in subnets:
        prefix = subnet.prefix.strip()
        if client_ip.startswith(prefix):
            return True

    return False


# =====================================================
# 1) STUDENT SELF CHECK-IN (must be on approved Wi-Fi)
# =====================================================
@attendance_bp.post("/check_in")
def check_in():
    data = request.get_json() or {}

    mac = (data.get("mac") or "").upper()
    session_id = data.get("session_id")

    if not mac or not session_id:
        return jsonify({"error": "missing_fields"}), 400

    # -------------------------
    # Get client’s actual source IP from request
    # -------------------------
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    print("DEBUG: Client IP =", client_ip)

    # -------------------------
    # Check Wi-Fi subnet
    # -------------------------
    if not ip_in_approved_subnet(client_ip):
        print("DEBUG: client not in approved subnet")
        return jsonify({"error": "You must be on classroom Wi-Fi"}), 403

    # -------------------------
    # Validate student by MAC
    # --------------------------
    student = Student.query.filter_by(mac_address=mac).first()
    if not student:
        return jsonify({"error": "unknown_device"}), 404

    # -------------------------
    # Validate session
    # -------------------------
    s = Session.query.get(session_id)
    if not s:
        return jsonify({"error": "session_not_found"}), 404

    # -------------------------
    # Insert attendance log
    # -------------------------
    log = AttendanceLog(
        session_id=session_id,
        student_id=student.id,
        mac=mac,
        status="Heartbeat",
        timestamp=datetime.utcnow()
    )

    db.session.add(log)
    db.session.commit()

    return jsonify({
        "message": "check_in_recorded",
        "student": student.name,
        "classroom_prefix": s.classroom.wifi_network_prefix
    }), 200


# =====================================================
# 2) ROUTER PUSH ENDPOINT (ADMIN ONLY)
# =====================================================
@attendance_bp.post("/router_push")
def router_push():
    if not require_admin_key():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    session_id = data.get("session_id")
    devices = data.get("connected_devices", [])

    s = Session.query.get(session_id)
    if not s:
        return jsonify({"error": "session_not_found"}), 404

    saved = 0

    for dev in devices:
        mac = (dev.get("mac") or "").upper()

        student = Student.query.filter_by(mac_address=mac).first()
        if not student:
            continue

        log = AttendanceLog(
            session_id=session_id,
            student_id=student.id,
            mac=mac,
            status="Heartbeat",
            timestamp=datetime.utcnow()
        )

        db.session.add(log)
        saved += 1

    db.session.commit()

    return jsonify({
        "message": "router_data_ingested",
        "count": saved
    }), 200


# =====================================================
# 3) INSTRUCTOR: GET ALL CHECK-INS FOR A SESSION
# =====================================================
@attendance_bp.get("/session/<int:session_id>")
def session_logs(session_id):
    logs = AttendanceLog.query.filter_by(
        session_id=session_id
    ).order_by(AttendanceLog.timestamp).all()

    out = [{
        "student_id": l.student_id,
        "mac": l.mac,
        "status": l.status,
        "timestamp": l.timestamp.isoformat()
    } for l in logs]

    return jsonify(out), 200

