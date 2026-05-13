from portfolio_ninja.domain.objects import AuditRecord


def render_report(audit_record: AuditRecord) -> str:
    lines = [
        "=" * 60,
        "portfolio_ninja — Cycle Report",
        "=" * 60,
        f"Cycle ID   : {audit_record.cycle_id}",
        f"Run Mode   : {audit_record.run_mode}",
        f"Completed  : {audit_record.completed_at.isoformat()}",
        f"Tickers    : {', '.join(audit_record.tickers)}",
        "",
        "Pipeline Lineage Hashes:",
    ]
    for key in sorted(audit_record.pipeline_hashes):
        lines.append(f"  {key:<22}: {audit_record.pipeline_hashes[key][:16]}...")
    lines += [
        "",
        f"Status     : {audit_record.validation_status}",
    ]
    if audit_record.reason_codes:
        lines.append(f"Reason codes: {', '.join(audit_record.reason_codes)}")
    lines.append("=" * 60)
    return "\n".join(lines)
