import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test():
    url = "https://www.ecajmer.ac.in/departments/cs-it/circulars"
    print(f"Connecting to {url} with domcontentloaded...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            # Wait until domcontentloaded, then wait 2 seconds for JS execution
            response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            print(f"Status: {response.status if response else 'None'}")
            await page.wait_for_timeout(3000)
            content = await page.content()
            print(f"Rendered HTML length: {len(content)}")
            
            soup = BeautifulSoup(content, "html.parser")
            print(f"Title: {soup.title.string if soup.title else 'No title'}")
            
            links = soup.find_all("a", href=True)
            print(f"Total links: {len(links)}")
            pdf_links = [a['href'] for a in links if '.pdf' in a['href'].lower() or 'download' in a['href'].lower()]
            print(f"PDF/Notice links: {len(pdf_links)}")
            for pl in pdf_links[:10]:
                print(f" - {pl}")
                
            tables = soup.find_all("table")
            print(f"Tables found: {len(tables)}")
            for t in tables[:2]:
                rows = t.find_all("tr")
                print(f" Table with {len(rows)} rows")
                for r in rows[:3]:
                    cells = [c.get_text().strip() for c in r.find_all(["th", "td"])]
                    print(f"   {cells}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

asyncio.run(test())
