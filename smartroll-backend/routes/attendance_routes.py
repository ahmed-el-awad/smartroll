from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, Student, Session, AttendanceLog, ApprovedSubnet
from sqlalchemy import desc
from routes.auth_routes import require_admin_key

attendance_bp = Blueprint("attendance_bp", __name__, url_prefix="/attendance")

# -------------------------
# Helper — Check if IP is allowed
# -------------------------
def ip_in_approved_subnet(client_ip: str) -> bool:
    if not client_ip:
        return False

    subnets = ApprovedSubnet.query.all()
    for subnet in subnets:
        prefix = subnet.prefix.strip()
        print("DEBUG-Subnet Check: Client IP =", client_ip, "Prefix =", prefix)
        if client_ip.startswith(prefix):
            return True

    return False


# -------------------------
# Helper — Check if student is currently checked in
# -------------------------
def is_student_checked_in(student_id: int, session_id: int) -> dict:
    """
    Check if a student is currently checked in to a session.
    Returns a dict with:
    - checked_in: bool
    - reason: str (explanation)
    - last_heartbeat: str or None (ISO format)
    - time_until_expiry: int or None (minutes)
    """
    now = datetime.utcnow()
    
    # Get session
    session = Session.query.get(session_id)
    if not session:
        return {
            "checked_in": False,
            "reason": "session_not_found",
            "last_heartbeat": None,
            "time_until_expiry": None
        }
    
    # Check if session is active
    if now < session.start_time:
        return {
            "checked_in": False,
            "reason": "session_not_started",
            "last_heartbeat": None,
            "time_until_expiry": None
        }
    
    if session.end_time and now > session.end_time:
        return {
            "checked_in": False,
            "reason": "session_ended",
            "last_heartbeat": None,
            "time_until_expiry": None
        }
    
    # Get most recent heartbeat for this student in this session
    last_log = AttendanceLog.query.filter_by(
        session_id=session_id,
        student_id=student_id
    ).order_by(desc(AttendanceLog.timestamp)).first()
    
    if not last_log:
        return {
            "checked_in": False,
            "reason": "no_heartbeat_recorded",
            "last_heartbeat": None,
            "time_until_expiry": None
        }
    
    # Calculate time since last heartbeat
    time_since_heartbeat = (now - last_log.timestamp).total_seconds() / 60  # minutes
    max_allowed_interval = session.heartbeat_minutes + session.grace_minutes
    
    if time_since_heartbeat <= max_allowed_interval:
        time_until_expiry = int(max_allowed_interval - time_since_heartbeat)
        return {
            "checked_in": True,
            "reason": "active",
            "last_heartbeat": last_log.timestamp.isoformat(),
            "time_until_expiry": time_until_expiry
        }
    else:
        return {
            "checked_in": False,
            "reason": "heartbeat_expired",
            "last_heartbeat": last_log.timestamp.isoformat(),
            "time_until_expiry": None
        }


# =====================================================
# 1) STUDENT SELF CHECK-IN
# =====================================================
@attendance_bp.post("/check_in")
def check_in():
    data = request.get_json() or {}

    mac = (data.get("mac") or "").upper()
    session_id = data.get("session_id")

    print("DEBUG-1: Incoming MAC =", mac)
    print("DEBUG-2: Incoming session_id =", session_id)

    if not mac or not session_id:
        return jsonify({"error": "missing_fields"}), 400

    # Receive real device IP from Flutter
    client_ip = data.get("device_ip") or request.remote_addr
    print("DEBUG-3: Client IP =", client_ip)

    # Subnet validation
    if not ip_in_approved_subnet(client_ip):
        print("DEBUG-4: Subnet FAILED")
        return jsonify({"error": "You must be on classroom Wi-Fi"}), 403

    print("DEBUG-4: Subnet OK")

    # Validate student
    student = Student.query.filter_by(mac_address=mac).first()
    print("DEBUG-5: Student =", student)

    if not student:
        return jsonify({"error": "unknown_device"}), 404

    # Validate session
    s = Session.query.get(session_id)
    print("DEBUG-6: Session =", s)

    if not s:
        return jsonify({"error": "session_not_found"}), 404

    # Validate session timing - check if current time is within session period
    now = datetime.utcnow()
    
    if now < s.start_time:
        return jsonify({
            "error": "Session has not started yet",
            "session_start_time": s.start_time.isoformat()
        }), 400
    
    if s.end_time and now > s.end_time:
        return jsonify({
            "error": "Session has ended",
            "session_end_time": s.end_time.isoformat()
        }), 400

    # Create log entry
    log = AttendanceLog(
        session_id=session_id,
        student_id=student.id,
        mac=mac,
        status="Heartbeat",
        timestamp=datetime.utcnow()
    )

    print("DEBUG-7: Log created:", log)

    # Commit safely
    try:
        db.session.add(log)
        db.session.commit()
        print("DEBUG-8: Commit OK")
    except Exception as e:
        print("DEBUG-8: Commit FAILED:", e)
        return jsonify({"error": "db_commit_failed"}), 500

    print("DEBUG-9: Total logs now =", AttendanceLog.query.count())

    # Check current status after recording heartbeat
    status = is_student_checked_in(student.id, session_id)

    return jsonify({
        "message": "check_in_recorded",
        "student": student.name,
        "checked_in": status["checked_in"],
        "reason": status["reason"],
        "last_heartbeat": status["last_heartbeat"],
        "time_until_expiry": status["time_until_expiry"]
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

    # Validate session timing - check if current time is within session period
    now = datetime.utcnow()
    
    if now < s.start_time:
        return jsonify({
            "error": "Session has not started yet",
            "session_start_time": s.start_time.isoformat()
        }), 400
    
    if s.end_time and now > s.end_time:
        return jsonify({
            "error": "Session has ended",
            "session_end_time": s.end_time.isoformat()
        }), 400

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
# 3) CHECK CURRENT STATUS (Student)
# =====================================================
@attendance_bp.get("/status")
def check_status():
    """
    Check if a student is currently checked in to a session.
    Query params: mac, session_id
    """
    mac = request.args.get("mac", "").upper()
    session_id = request.args.get("session_id", type=int)

    if not mac or not session_id:
        return jsonify({"error": "missing_fields"}), 400

    # Validate student
    student = Student.query.filter_by(mac_address=mac).first()
    if not student:
        return jsonify({"error": "unknown_device"}), 404

    # Check status
    status = is_student_checked_in(student.id, session_id)

    return jsonify({
        "student_id": student.id,
        "student_name": student.name,
        "session_id": session_id,
        "checked_in": status["checked_in"],
        "reason": status["reason"],
        "last_heartbeat": status["last_heartbeat"],
        "time_until_expiry": status["time_until_expiry"]
    }), 200


# =====================================================
# 4) INSTRUCTOR VIEW LOGS (Newest → Oldest)
# =====================================================
@attendance_bp.get("/session/<int:session_id>")
def session_logs(session_id):
    logs = AttendanceLog.query.filter_by(
        session_id=session_id
    ).order_by(desc(AttendanceLog.timestamp)).all()

    out = [{
        "student_id": l.student_id,
        "mac": l.mac,
        "status": l.status,
        "timestamp": l.timestamp.isoformat()
    } for l in logs]

    return jsonify(out), 200
