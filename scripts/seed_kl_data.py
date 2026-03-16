"""
Seed Knowledge Layer with Banking Test Documents
==================================================

Reads downloaded banking PDFs from ``data/banking_docs/`` and pushes
them to the Knowledge Layer API as documents with:
- Structured metadata (domain, action_class, phase_label, tags, event_date)
- File versions with content
- Chunks per document version
- A snapshot pinning all seeded documents

Usage::

    # First download the docs
    python scripts/download_banking_docs.py

    # Then seed KL (requires admin key for tenant/api-key setup)
    python scripts/seed_kl_data.py --admin-key kla_xxx

    # Or with existing API key
    python scripts/seed_kl_data.py --api-key kl_xxx

    # Dry run
    python scripts/seed_kl_data.py --dry-run

    # Custom KL URL
    python scripts/seed_kl_data.py --api-key kl_xxx --base-url http://localhost:8000
"""

import argparse
import os
import sys
import hashlib
import re
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from hpvd.adapters.kl_client import KLClient, DocumentMetadata


# ---------------------------------------------------------------------------
# Document type classification based on filename patterns
# ---------------------------------------------------------------------------

DOC_TYPE_MAP = {
    "intimazione": "INTIMAZIONE",
    "intimaz": "INTIMAZIONE",
    "consegna pec": "PEC_RECEIPT",
    "ricevuta": "PEC_RECEIPT",
    "precisazione del credito": "CREDIT_SPECIFICATION",
    "precisazione": "CREDIT_SPECIFICATION",
    "allegato 4": "IDENTITY_DOC",
    "patente": "IDENTITY_DOC",
    "documento": "IDENTITY_DOC",
    "doc identit": "IDENTITY_DOC",
    "delibera": "DELIBERA",
    "contratto": "CONTRACT",
    "finanziamento": "CONTRACT",
    "erogazione": "EROGAZIONE",
    "piano industriale": "INDUSTRIAL_PLAN",
    "piano": "AMMORTAMENTO",
    "ammortamento": "AMMORTAMENTO",
    "dichiarazione rischio": "RISK_DECLARATION",
    "dichiarazione tasso": "RATE_DECLARATION",
    "no concordato": "COMPLIANCE",
    "assenza inadempienze": "NO_DEFAULT",
    "no difficolt": "NO_DEFAULT",
    "assenza pregiudizievoli": "NO_PREJUDICE",
    "cr ": "CREDIT_REPORT",
    "centrale rischi": "CREDIT_REPORT",
    "ce.ri": "CREDIT_REPORT",
    "check_escussione": "ESCUSSIONE_CHECK",
    "letteraesito": "ESITO_LETTER",
    "visura": "PROPERTY_SURVEY",
    "fidejussione": "FIDEJUSSIONE",
    "fid.gen": "FIDEJUSSIONE",
    "bilancio": "BALANCE_SHEET",
    "lettera": "ESITO_LETTER",
    "recap": "CREDIT_SPECIFICATION",
}


# Document type → action_class mapping
DOC_TYPE_TO_ACTION = {
    "INTIMAZIONE": "DEBT_COLLECTION",
    "PEC_RECEIPT": "DEBT_COLLECTION",
    "CREDIT_SPECIFICATION": "CREDIT_ANALYSIS",
    "IDENTITY_DOC": "KYC_VERIFICATION",
    "DELIBERA": "CREDIT_APPROVAL",
    "CONTRACT": "TRADE_EXECUTION",
    "EROGAZIONE": "DISBURSEMENT",
    "AMMORTAMENTO": "REPAYMENT_PLAN",
    "CREDIT_REPORT": "RISK_ASSESSMENT",
    "RISK_DECLARATION": "RISK_ASSESSMENT",
    "RATE_DECLARATION": "RISK_ASSESSMENT",
    "NO_DEFAULT": "COMPLIANCE_CHECK",
    "NO_PREJUDICE": "COMPLIANCE_CHECK",
    "ESITO_LETTER": "OUTCOME_NOTIFICATION",
    "ESCUSSIONE_CHECK": "CREDIT_ANALYSIS",
    "INDUSTRIAL_PLAN": "FINANCIAL_PLANNING",
    "PROPERTY_SURVEY": "COLLATERAL_ASSESSMENT",
    "FIDEJUSSIONE": "GUARANTEE_ISSUANCE",
    "BALANCE_SHEET": "FINANCIAL_PLANNING",
}

# Document type → phase_label mapping
DOC_TYPE_TO_PHASE = {
    "INTIMAZIONE": "EXECUTION_PHASE",
    "PEC_RECEIPT": "EXECUTION_PHASE",
    "CREDIT_SPECIFICATION": "ANALYSIS_PHASE",
    "IDENTITY_DOC": "VERIFICATION_PHASE",
    "DELIBERA": "DECISION_PHASE",
    "CONTRACT": "EXECUTION_PHASE",
    "EROGAZIONE": "EXECUTION_PHASE",
    "AMMORTAMENTO": "PLANNING_PHASE",
    "CREDIT_REPORT": "ANALYSIS_PHASE",
    "RISK_DECLARATION": "ANALYSIS_PHASE",
    "RATE_DECLARATION": "ANALYSIS_PHASE",
    "NO_DEFAULT": "VERIFICATION_PHASE",
    "NO_PREJUDICE": "VERIFICATION_PHASE",
    "ESITO_LETTER": "COMPLETION_PHASE",
    "ESCUSSIONE_CHECK": "ANALYSIS_PHASE",
    "INDUSTRIAL_PLAN": "PLANNING_PHASE",
    "PROPERTY_SURVEY": "ANALYSIS_PHASE",
    "FIDEJUSSIONE": "EXECUTION_PHASE",
    "BALANCE_SHEET": "ANALYSIS_PHASE",
}


def classify_document(filename: str) -> str:
    """Classify a document based on its filename."""
    lower = filename.lower()
    for pattern, doc_type in DOC_TYPE_MAP.items():
        if pattern in lower:
            return doc_type
    return "OTHER"


def extract_date_from_filename(filename: str) -> str | None:
    """Try to extract a date from the filename (dd-mm-yyyy format)."""
    match = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return None


def build_metadata(doc_type: str, filename: str, case_id: str) -> DocumentMetadata:
    """Build structured metadata for a document."""
    action_class = DOC_TYPE_TO_ACTION.get(doc_type, doc_type)
    phase_label = DOC_TYPE_TO_PHASE.get(doc_type, "UNKNOWN_PHASE")
    event_date = extract_date_from_filename(filename)

    tags = [doc_type.lower()]
    tags.append(f"case_{case_id}")

    return DocumentMetadata(
        domain="finance",
        action_class=action_class,
        phase_label=phase_label,
        tags=tags,
        event_date=event_date,
    )


def simple_chunk_text(text: str, max_chunk_size: int = 500) -> list[dict]:
    """
    Split text into chunks of roughly max_chunk_size characters.

    Returns list of dicts ready for KL create_chunks API.
    """
    if not text:
        return []

    chunks = []
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    current = ""
    seq = 1

    for para in paragraphs:
        if len(current) + len(para) > max_chunk_size and current:
            chunks.append({
                "chunk_id": f"c{seq:02d}",
                "content": current.strip(),
                "sequence": seq,
                "metadata": {},
            })
            seq += 1
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append({
            "chunk_id": f"c{seq:02d}",
            "content": current.strip(),
            "sequence": seq,
            "metadata": {},
        })

    return chunks


CREATED_BY = "seed_script_v2"


def seed_case_folder(
    client: KLClient,
    case_id: str,
    folder_path: str,
    dry_run: bool = False,
) -> list[dict]:
    """
    Seed all documents from a single case folder.

    Returns list of {document_id, version_number} for snapshot creation.
    """
    files = sorted([
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and not f.startswith(".")
    ])

    if not files:
        print(f"  [SKIP] No files in {case_id}")
        return []

    seeded_items = []
    for filename in files:
        filepath = os.path.join(folder_path, filename)

        # Skip non-PDF files
        if not filename.lower().endswith(".pdf"):
            print(f"  [SKIP] {filename} (not PDF)")
            continue

        doc_type = classify_document(filename)
        title = f"[{case_id}] {filename}"
        metadata = build_metadata(doc_type, filename, case_id)

        if dry_run:
            print(f"  [DRY] Would create: {title} (type={doc_type}, action={metadata.action_class})")
            seeded_items.append({"document_id": "dry-run", "version_number": 1})
            continue

        try:
            # Create document with metadata
            doc = client.create_document(
                title=title,
                document_type=doc_type,
                metadata=metadata,
                created_by=CREATED_BY,
            )
            print(f"  [OK] Created document: {doc.id} — {title}")
            print(f"       type={doc_type} action={metadata.action_class} phase={metadata.phase_label}")

            # Upload file as version 1
            with open(filepath, "rb") as f:
                file_bytes = f.read()

            # Do NOT pass raw_text here — it triggers KL auto-chunking
            # which conflicts with our explicit chunk creation below
            version = client.upload_version(
                document_id=doc.id,
                file_content=file_bytes,
                filename=filename,
                uploaded_by=CREATED_BY,
            )
            print(f"       Version {version.version_number} uploaded ({version.file_size} bytes)")

            # Create chunks explicitly with metadata
            raw_text = f"{title}. Document type: {doc_type}. Domain: finance. Action: {metadata.action_class}."
            chunk_defs = simple_chunk_text(raw_text)
            for cd in chunk_defs:
                cd["metadata"] = {
                    "action_class": metadata.action_class,
                    "phase_label": metadata.phase_label,
                    "case_id": case_id,
                }

            if chunk_defs:
                try:
                    kl_chunks = client.create_chunks(
                        document_id=doc.id,
                        version_number=version.version_number,
                        chunks=chunk_defs,
                    )
                    print(f"       {len(kl_chunks)} chunks created")
                except Exception as chunk_err:
                    print(f"       [WARN] Chunk creation failed: {chunk_err}")

            seeded_items.append({
                "document_id": doc.id,
                "version_number": version.version_number,
            })

        except Exception as e:
            print(f"  [ERR] Failed: {filename} — {e}")

    return seeded_items


def seed_snapshot(
    client: KLClient,
    items: list[dict],
    dry_run: bool = False,
) -> None:
    """Create an immutable snapshot pinning all seeded documents."""
    if not items:
        print("\n[SKIP] No items to snapshot")
        return

    snapshot_id = f"PINSET_{datetime.now().strftime('%Y%m%d_%H%M')}"

    if dry_run:
        print(f"\n[DRY] Would create snapshot: {snapshot_id} with {len(items)} items")
        return

    try:
        snapshot = client.create_snapshot(
            snapshot_id=snapshot_id,
            ontology_version="ontology_finance_v1",
            calibration_model_version="calib_v1",
            items=items,
            description=f"Seed snapshot with {len(items)} banking documents",
            created_by=CREATED_BY,
        )
        print(f"\n[OK] Snapshot created: {snapshot.snapshot_id}")
        print(f"     ID: {snapshot.id}")
        print(f"     Items: {len(snapshot.items)}")
        print(f"     Ontology: {snapshot.ontology_version}")
        print(f"     Calibration: {snapshot.calibration_model_version}")
    except Exception as e:
        print(f"\n[ERR] Failed to create snapshot: {e}")


def seed_event(
    client: KLClient,
    case_ids: list,
    snapshot_id: str | None = None,
    dry_run: bool = False,
) -> None:
    """Create a KNOWLEDGE_SNAPSHOT_PINNED event recording this seed."""
    if dry_run:
        print(f"\n[DRY] Would create event for {len(case_ids)} cases")
        return

    try:
        event = client.create_event(
            event_kind="KNOWLEDGE_SNAPSHOT_PINNED",
            payload={
                "description": "Seed of banking test documents with metadata and chunks",
                "case_ids": case_ids,
                "total_cases": len(case_ids),
                "snapshot_id": snapshot_id,
                "source": "Google Drive Banking_docs",
                "seed_version": "v2",
            },
            commit_id=f"seed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            created_by=CREATED_BY,
        )
        print(f"\n[OK] Event created: {event.id} (hash={event.event_hash})")
    except Exception as e:
        print(f"\n[ERR] Failed to create event: {e}")


def setup_tenant(client: KLClient, tenant_id: str) -> str | None:
    """
    Ensure tenant exists and create an API key.

    Returns the raw API key string, or None if creation failed.
    """
    # Check if tenant exists
    try:
        tenants = client.list_tenants()
        existing = [t for t in tenants if t.id == tenant_id]
        if existing:
            print(f"[OK] Tenant '{tenant_id}' already exists")
        else:
            tenant = client.create_tenant(name=tenant_id, tenant_id=tenant_id)
            print(f"[OK] Created tenant: {tenant.id}")
    except Exception as e:
        print(f"[ERR] Tenant setup failed: {e}")
        return None

    # Create API key
    try:
        api_key = client.create_api_key(
            tenant_id=tenant_id,
            name="hpvd_seed_key",
        )
        print(f"[OK] API key created: {api_key.key_prefix}... (save this!)")
        print(f"     Raw key: {api_key.raw_key}")
        return api_key.raw_key
    except Exception as e:
        print(f"[ERR] API key creation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Seed KL with banking test documents")
    parser.add_argument(
        "--base-url",
        default=KLClient.DEFAULT_BASE_URL,
        help="Knowledge Layer API base URL",
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "banking_docs",
        ),
        help="Path to downloaded banking docs",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("KL_API_KEY"),
        help="KL tenant API key (kl_...). Can also be set via KL_API_KEY env var.",
    )
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("KL_ADMIN_KEY"),
        help="KL admin key (kla_...) for tenant/api-key setup. Can also be set via KL_ADMIN_KEY env var.",
    )
    parser.add_argument(
        "--setup-tenant",
        action="store_true",
        help="Create tenant and API key before seeding (requires --admin-key)",
    )
    parser.add_argument(
        "--tenant-id",
        default="BANKING_CORE",
        help="Tenant ID to use (default: BANKING_CORE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making API calls",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"ERROR: Data directory not found: {args.data_dir}")
        print(f"Run 'python scripts/download_banking_docs.py' first.")
        sys.exit(1)

    # Find case subfolders (numeric folder names)
    case_folders = sorted([
        d for d in os.listdir(args.data_dir)
        if os.path.isdir(os.path.join(args.data_dir, d))
        and d.isdigit()
    ])

    if not case_folders:
        print(f"ERROR: No case folders found in {args.data_dir}")
        sys.exit(1)

    print(f"Knowledge Layer Seed Script v2")
    print(f"==============================")
    print(f"  KL API    : {args.base_url}")
    print(f"  Data      : {args.data_dir}")
    print(f"  Cases     : {len(case_folders)} ({', '.join(case_folders)})")
    print(f"  Tenant    : {args.tenant_id}")
    print(f"  Dry run   : {args.dry_run}")
    print()

    api_key = args.api_key

    # Step 0: Tenant setup (if requested)
    if args.setup_tenant:
        if not args.admin_key:
            print("ERROR: --admin-key required for --setup-tenant")
            sys.exit(1)
        with KLClient(base_url=args.base_url, admin_key=args.admin_key) as admin_client:
            raw_key = setup_tenant(admin_client, args.tenant_id)
            if raw_key:
                api_key = raw_key
                print(f"\n  Using new API key for seeding\n")
            else:
                print("ERROR: Could not create API key")
                sys.exit(1)

    if not api_key and not args.dry_run:
        print("ERROR: No API key. Use --api-key, KL_API_KEY env var, or --setup-tenant")
        sys.exit(1)

    with KLClient(base_url=args.base_url, api_key=api_key) as client:
        # Health check
        if not args.dry_run:
            try:
                health = client.health_check()
                print(f"[OK] KL API reachable: {health}")
            except Exception as e:
                print(f"[ERR] KL API not reachable: {e}")
                sys.exit(1)

        all_items = []
        for case_id in case_folders:
            folder_path = os.path.join(args.data_dir, case_id)
            print(f"\nCase {case_id}:")
            items = seed_case_folder(client, case_id, folder_path, dry_run=args.dry_run)
            all_items.extend(items)

        # Create snapshot
        seed_snapshot(client, all_items, dry_run=args.dry_run)

        # Create event
        seed_event(client, case_folders, dry_run=args.dry_run)

        print(f"\n{'='*40}")
        print(f"Total documents seeded: {len(all_items)}")
        if api_key and not args.dry_run:
            print(f"\nTo use this API key in your code:")
            print(f'  export KL_API_KEY="{api_key}"')
        print(f"Done!")


if __name__ == "__main__":
    main()
