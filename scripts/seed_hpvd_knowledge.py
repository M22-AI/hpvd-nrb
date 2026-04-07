# -*- coding: utf-8 -*-
"""
Seed HPVD Knowledge Objects ke Knowledge Layer
===============================================

Upload file JSON knowledge objects ke KL sehingga bisa di-load oleh
KLCorpusLoader saat HPVD API startup.

Setiap file JSON harus punya salah satu key berikut di level root:
    policy_id       -> object_type = policy
    product_id      -> object_type = product
    mapping_id      -> object_type = rule_mapping
    doc_type        -> object_type = document_schema

Usage::

    python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge
    python scripts/seed_hpvd_knowledge.py --files data/policy.json data/product.json
    python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge --dry-run
    python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge --api-key kl_xxx
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from hpvd.adapters.kl_client import DocumentMetadata, KLClient

_INFER_MAP = [
    ("policy_id", "policy"),
    ("product_id", "product"),
    ("mapping_id", "rule_mapping"),
    ("doc_type", "document_schema"),
]

CREATED_BY = "seed_hpvd_knowledge_v1"


def infer_object_type(obj):
    for key, otype in _INFER_MAP:
        if key in obj:
            return otype
    return None


def infer_title(obj, object_type):
    id_fields = {
        "policy": "policy_id",
        "product": "product_id",
        "rule_mapping": "mapping_id",
        "document_schema": "doc_type",
    }
    if object_type:
        id_val = obj.get(id_fields.get(object_type, ""), "unknown")
        name = obj.get("name", "")
        return "[hpvd][{}] {}{}".format(object_type, id_val, " -- " + name if name else "")
    return "[hpvd] {}".format(list(obj.keys())[:3])


def upload_knowledge_object(client, obj, domain, dry_run=False):
    object_type = infer_object_type(obj)
    if object_type is None:
        print("  [SKIP] Tidak bisa infer object_type dari keys: {}".format(list(obj.keys())))
        return False

    title = infer_title(obj, object_type)
    raw_text = json.dumps(obj, ensure_ascii=False)

    if dry_run:
        print("  [DRY]  {}  (type={})".format(title, object_type))
        return True

    try:
        doc = client.create_document(
            title=title,
            document_type="string",
            metadata=DocumentMetadata(domain=domain),
            created_by=CREATED_BY,
        )
        print("  [OK]   Document created: {}".format(doc.id))

        dummy_bytes = raw_text.encode("utf-8")
        version = client.upload_version(
            document_id=doc.id,
            file_content=dummy_bytes,
            filename="{}.json".format(object_type),
            raw_text=raw_text,
            uploaded_by=CREATED_BY,
        )
        print("         Version {} uploaded -- {}".format(version.version_number, title))
        return True

    except Exception as exc:
        print("  [ERR]  Gagal upload '{}': {}".format(title, exc))
        return False


def collect_json_files(paths):
    result = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            result.extend(sorted(path.glob("*.json")))
        elif path.is_file() and path.suffix == ".json":
            result.append(path)
        else:
            print("[WARN] Path tidak ditemukan atau bukan .json: {}".format(p))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Upload HPVD knowledge objects (JSON) ke Knowledge Layer"
    )
    parser.add_argument("--dir", help="Folder berisi file .json knowledge objects")
    parser.add_argument("--files", nargs="+", metavar="FILE", help="Satu atau lebih file .json")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("KL_API_KEY"),
        help="KL tenant API key (kl_...). Default: dari KL_API_KEY env var / .env",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("KL_BASE_URL", "https://knowledge-layer-production.up.railway.app"),
        help="KL base URL",
    )
    parser.add_argument(
        "--domain",
        default=os.environ.get("KL_DOMAIN", "banking"),
        help="Domain/sector (default: banking)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print saja, tidak beneran upload")
    args = parser.parse_args()

    paths = []
    if args.dir:
        paths.append(args.dir)
    if args.files:
        paths.extend(args.files)
    if not paths:
        parser.error("Harus berikan --dir atau --files")

    json_files = collect_json_files(paths)
    if not json_files:
        print("Tidak ada file .json ditemukan.")
        sys.exit(1)

    print("HPVD Knowledge Seed")
    print("===================")
    print("  KL URL   : {}".format(args.base_url))
    print("  Domain   : {}".format(args.domain))
    print("  Files    : {}".format(len(json_files)))
    print("  Dry run  : {}".format(args.dry_run))
    print()

    if not args.api_key and not args.dry_run:
        print("ERROR: KL_API_KEY tidak ditemukan. Set via --api-key atau .env")
        sys.exit(1)

    success = 0
    failed = 0

    with KLClient(base_url=args.base_url, api_key=args.api_key) as client:
        if not args.dry_run:
            try:
                health = client.health_check()
                print("[OK] KL API reachable: {}\n".format(health))
            except Exception as exc:
                print("[ERR] KL API tidak bisa dijangkau: {}".format(exc))
                sys.exit(1)

        for json_file in json_files:
            print("File: {}".format(json_file.name))
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                print("  [ERR] Tidak bisa baca file: {}".format(exc))
                failed += 1
                continue

            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                ok = upload_knowledge_object(client, obj, args.domain, dry_run=args.dry_run)
                if ok:
                    success += 1
                else:
                    failed += 1

    print()
    print("=" * 40)
    print("Berhasil : {}".format(success))
    print("Gagal    : {}".format(failed))
    print("Done!")
    print()
    print("Restart HPVD API agar corpus ter-reload:")
    print("  uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8000 --reload")


if __name__ == "__main__":
    main()