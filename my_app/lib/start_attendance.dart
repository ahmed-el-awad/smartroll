import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';

import 'data/base_url.dart';

class StartAttendancePage extends StatefulWidget {
  const StartAttendancePage({super.key});

  @override
  State<StartAttendancePage> createState() => _StartAttendancePageState();
}

class _StartAttendancePageState extends State<StartAttendancePage> {
  bool isLoading = false;
  bool isCheckingIn = false;
  Timer? _pollTimer;
  Map<String, dynamic>? _sessionDetails;
  Map<String, dynamic>? _currentStatus;
  bool _isPolling = false;

  // Hardcoded for now — you can replace these with real values later
  final String macAddress = "AA:BB:CC:DD:EE:FF"; // Example
  final int sessionId = 1; // Example

  @override
  void initState() {
    super.initState();
    _fetchSessionDetails();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _fetchSessionDetails() async {
    try {
      final response = await http.get(
        Uri.parse("http://$baseURL/sessions/$sessionId"),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _sessionDetails = data;
        });
        // Start polling after fetching session details
        _startPolling();
        // Also check status immediately
        _checkStatus();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Failed to load session details"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Error loading session: $e"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _startPolling() {
    if (_sessionDetails == null || _isPolling) return;

    final heartbeatMinutes = _sessionDetails!['heartbeat_minutes'] ?? 10;
    // Poll at half the heartbeat interval to ensure we catch status changes quickly
    final pollIntervalSeconds = (heartbeatMinutes * 60 / 2).round();
    
    setState(() => _isPolling = true);

    _pollTimer = Timer.periodic(Duration(seconds: pollIntervalSeconds), (timer) {
      _checkStatus();
    });
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    setState(() => _isPolling = false);
  }

  Future<void> _checkStatus() async {
    try {
      final response = await http.get(
        Uri.parse("http://$baseURL/attendance/status?mac=${Uri.encodeComponent(macAddress)}&session_id=$sessionId"),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _currentStatus = data;
        });
      }
    } catch (e) {
      // Silently fail for polling - don't show error for every poll
      print("Status check error: $e");
    }
  }

  Future<void> _checkIn() async {
    setState(() => isCheckingIn = true);

    try {
      final response = await http.post(
        Uri.parse("http://$baseURL/attendance/check_in"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"mac": macAddress, "session_id": sessionId}),
      );

      setState(() => isCheckingIn = false);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Update status from response
        setState(() {
          _currentStatus = {
            "checked_in": data['checked_in'],
            "reason": data['reason'],
            "last_heartbeat": data['last_heartbeat'],
            "time_until_expiry": data['time_until_expiry'],
          };
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Check-in recorded for ${data['student']}"),
            backgroundColor: Colors.green,
          ),
        );

        // Refresh status after check-in
        _checkStatus();
      } else if (response.statusCode == 400) {
        // Session timing errors (not started, ended, etc.)
        final data = jsonDecode(response.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(data['error'] ?? "Invalid request"),
            backgroundColor: Colors.orange,
            duration: const Duration(seconds: 4),
          ),
        );
        // Refresh status to update UI
        _checkStatus();
      } else if (response.statusCode == 403) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("You must be on classroom Wi-Fi"),
            backgroundColor: Colors.red,
          ),
        );
      } else if (response.statusCode == 404) {
        final data = jsonDecode(response.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(data['error']), backgroundColor: Colors.red),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Server error: ${response.statusCode}"),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      setState(() => isCheckingIn = false);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Network error: $e"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  String _getStatusText() {
    if (_currentStatus == null) {
      return "Loading status...";
    }

    final checkedIn = _currentStatus!['checked_in'] ?? false;
    final reason = _currentStatus!['reason'] ?? 'unknown';
    final timeUntilExpiry = _currentStatus!['time_until_expiry'];

    if (checkedIn) {
      if (timeUntilExpiry != null) {
        return "Checked In • Expires in ${timeUntilExpiry} min";
      }
      return "Checked In";
    } else {
      switch (reason) {
        case 'session_not_started':
          return "Session not started yet";
        case 'session_ended':
          return "Session has ended";
        case 'heartbeat_expired':
          return "Check-in expired • Please check in again";
        case 'no_heartbeat_recorded':
          return "Not checked in";
        default:
          return "Not checked in";
      }
    }
  }

  Color _getStatusColor() {
    if (_currentStatus == null) {
      return Colors.grey;
    }

    final checkedIn = _currentStatus!['checked_in'] ?? false;
    return checkedIn ? Colors.green : Colors.orange;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text(
          "Check-In",
          style: TextStyle(color: Colors.black, fontWeight: FontWeight.w600),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.black),
      ),
      body: Padding(
        padding: const EdgeInsets.all(25),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              "Attendance Check-In",
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              "Press the button below to check in.\nMake sure you're connected to classroom Wi-Fi.",
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
            const SizedBox(height: 40),

            // Status Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _getStatusColor().withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _getStatusColor().withOpacity(0.3),
                  width: 2,
                ),
              ),
              child: Column(
                children: [
                  Icon(
                    _currentStatus?['checked_in'] == true
                        ? Icons.check_circle
                        : Icons.access_time,
                    color: _getStatusColor(),
                    size: 48,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _getStatusText(),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: _getStatusColor(),
                    ),
                  ),
                  if (_sessionDetails != null && _currentStatus != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      "Heartbeat interval: ${_sessionDetails!['heartbeat_minutes']} min",
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.grey,
                      ),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 40),

            ElevatedButton(
              onPressed: (isCheckingIn || isLoading) ? null : _checkIn,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6DB0A5),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(40),
                ),
                minimumSize: const Size(double.infinity, 70),
              ),
              child: (isCheckingIn || isLoading)
                  ? const CircularProgressIndicator(color: Colors.white)
                  : const Text(
                      "Check In",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),

            if (_isPolling) ...[
              const SizedBox(height: 20),
              const Text(
                "Status is being monitored automatically",
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
