from logwindow import count_levels


def test_counts_lines_of_records_in_window():
    lines = [
        "2026-03-01T09:15:00Z INFO service started",
        "2026-03-01T10:05:00Z ERROR request failed",
        "Traceback (most recent call last):",
        "2026-03-01T10:20:00Z INFO request retried",
        "2026-03-01T12:40:00Z INFO service stopped",
    ]
    result = count_levels(lines, "2026-03-01T10:00:00Z", "2026-03-01T11:00:00Z")
    assert result == {"ERROR": 2, "INFO": 1}
