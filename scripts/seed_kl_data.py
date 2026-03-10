"""
Seed Knowledge Layer with Banking Test Documents
==================================================

Reads downloaded banking PDFs from ``data/banking_docs/`` and pushes
them to the Knowledge Layer API as documents with file versions.

Each subfolder (case ID) becomes a logical grouping. Each PDF within
a subfolder becomes a document with its file uploaded as version 1.

Usage::

    # First download the docs
    python scripts/download_banking_docs.py

    # Then seed KL
    python scripts/seed_kl_data.py

    # Or with a custom KL URL
    python scripts/seed_kl_data.py --base-url http://localhost:8000
"""

import argparse
import os
import sys
import hashlib

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from hpvd.adapters.kl_client import KLClient


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
    "piano": "AMMORTAMENTO",
    "ammortamento": "AMMORTAMENTO",
    "piano industriale": "INDUSTRIAL_PLAN",
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


def classify_document(filename: str) -> str:
    """Classify a document based on its filename."""
    lower = filename.lower()
    for pattern, doc_type in DOC_TYPE_MAP.items():
        if pattern in lower:
            return doc_type
    return "OTHER"


TENANT_ID = "BANKING_CORE"
CREATED_BY = "seed_script_v1"


def seed_case_folder(client: KLClient, case_id: str, folder_path: str, dry_run: bool = False):
    """Seed all documents from a single case folder."""
    files = sorted([
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and not f.startswith(".")
    ])

    if not files:
        print(f"  [SKIP] No files in {case_id}")
        return 0

    count = 0
    for filename in files:
        filepath = os.path.join(folder_path, filename)

        # Skip non-PDF files (e.g., .xlsm) for now
        if not filename.lower().endswith(".pdf"):
            print(f"  [SKIP] {filename} (not PDF)")
            continue

        doc_type = classify_document(filename)
        title = f"[{case_id}] {filename}"

        if dry_run:
            print(f"  [DRY] Would create: {title} (type={doc_type})")
            count += 1
            continue

        try:
            # Create document
            doc = client.create_document(
                tenant_id=TENANT_ID,
                title=title,
                document_type=doc_type,
                created_by=CREATED_BY,
            )
            print(f"  [OK] Created document: {doc.id} — {title} (type={doc_type})")

            # Upload file as version 1
            with open(filepath, "rb") as f:
                file_bytes = f.read()

            version = client.upload_version(
                document_id=doc.id,
                file_content=file_bytes,
                filename=filename,
                uploaded_by=CREATED_BY,
            )
            print(f"       Version {version.version_number} uploaded ({version.file_size} bytes, sha256={version.checksum_sha256})")
            count += 1

        except Exception as e:
            print(f"  [ERR] Failed: {filename} — {e}")

    return count


def seed_event_snapshot(client: KLClient, case_ids: list, dry_run: bool = False):
    """Create a KNOWLEDGE_SNAPSHOT_PINNED event recording this seed."""
    if dry_run:
        print(f"\n[DRY] Would create snapshot event for {len(case_ids)} cases")
        return

    try:
        event = client.create_event(
            tenant_id=TENANT_ID,
            event_kind="KNOWLEDGE_SNAPSHOT_PINNED",
            payload={
                "description": "Initial seed of banking test documents",
                "case_ids": case_ids,
                "total_cases": len(case_ids),
                "source": "Google Drive Banking_docs",
            },
            created_by=CREATED_BY,
        )
        print(f"\n[OK] Snapshot event created: {event.id} (hash={event.event_hash})")
    except Exception as e:
        print(f"\n[ERR] Failed to create snapshot event: {e}")


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

    print(f"Knowledge Layer Seed Script")
    print(f"===========================")
    print(f"  KL API  : {args.base_url}")
    print(f"  Data    : {args.data_dir}")
    print(f"  Cases   : {len(case_folders)} ({', '.join(case_folders)})")
    print(f"  Tenant  : {TENANT_ID}")
    print(f"  Dry run : {args.dry_run}")
    print()

    with KLClient(base_url=args.base_url) as client:
        # Health check
        if not args.dry_run:
            try:
                health = client.health_check()
                print(f"[OK] KL API reachable: {health}")
            except Exception as e:
                print(f"[ERR] KL API not reachable: {e}")
                sys.exit(1)

        total = 0
        for case_id in case_folders:
            folder_path = os.path.join(args.data_dir, case_id)
            print(f"\nCase {case_id}:")
            count = seed_case_folder(client, case_id, folder_path, dry_run=args.dry_run)
            total += count

        # Create snapshot event
        seed_event_snapshot(client, case_folders, dry_run=args.dry_run)

        print(f"\n{'='*40}")
        print(f"Total documents seeded: {total}")
        print(f"Done!")


if __name__ == "__main__":
    main()
