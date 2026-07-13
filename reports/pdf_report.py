"""Generate PDF reports (placeholder)."""
def to_pdf(report, out_path):
    with open(out_path, "wb") as f:
        f.write(report.encode("utf-8"))
    return out_path
