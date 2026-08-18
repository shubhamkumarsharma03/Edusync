import asyncio
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from ingestion.fetchers.factory import fetch_document


async def test_live_fetch(url: str) -> None:
    print("\n" + "=" * 60)
    print(f"Fetching live document from: {url}")
    print("=" * 60)

    try:
        doc = await fetch_document(url)
        print("\n[+] Successfully fetched and parsed page!")
        print(f" - Source Type: {doc.source_type}")
        print(f" - Page Title: {doc.metadata.get('title')}")
        print(f" - Dynamic Rendered: {doc.metadata.get('dynamic_rendered', False)}")
        print(f" - Raw Rendered Size: {len(doc.raw_content)} bytes")
        print(f" - Extracted Text Length: {len(doc.extracted_text)} characters")
        print(f" - Extracted Tables Count: {len(doc.tables)}")

        pdf_links = doc.metadata.get("discovered_pdf_links", [])
        print(f" - Discovered PDF Circular Links: {len(pdf_links)}")
        if pdf_links:
            print("\n--- Discovered PDF Circular Links (First 5) ---")
            for idx, link in enumerate(pdf_links[:5], 1):
                print(f"  {idx}. {link}")

        print("\n--- Extracted Text Preview (First 800 chars) ---")
        preview = doc.extracted_text[:800] if doc.extracted_text else "[Empty extracted text]"
        print(preview)

        # Test fetching one of the discovered real PDF circulars
        if pdf_links:
            first_pdf = pdf_links[0]
            print("\n" + "=" * 60)
            print(f"Testing PDF Fetcher on live circular: {first_pdf}")
            print("=" * 60)
            try:
                pdf_doc = await fetch_document(first_pdf)
                print("[+] Successfully fetched and parsed real PDF circular!")
                print(f" - Title: {pdf_doc.metadata.get('title') or 'N/A'}")
                print(f" - Page Count: {pdf_doc.metadata.get('page_count')}")
                print(f" - Table Count: {pdf_doc.metadata.get('table_count')}")
                print(f" - File Size: {len(pdf_doc.raw_content)} bytes")
                print("\n--- Extracted PDF Text Sample ---")
                print(pdf_doc.extracted_text[:800] if pdf_doc.extracted_text else "[No text extracted]")
            except Exception as pdf_err:
                print(f"[-] Error fetching sample PDF {first_pdf}: {pdf_err}")

    except Exception as e:
        print(f"[-] Error fetching {url}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.ecajmer.ac.in/departments/cs-it/circulars"
    asyncio.run(test_live_fetch(target_url))
