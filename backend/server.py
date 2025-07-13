from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import requests
import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from typing import List, Dict, Optional
import uuid
from datetime import datetime
import re
from pathlib import Path

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Custom Search API credentials
GOOGLE_API_KEY = "AIzaSyAsoKcq2DMgtRw-L_3inX9Cq-V6-YNOAVg"
SEARCH_ENGINE_ID = "2701a7d64a00d47fd"

# In-memory storage for job progress
job_progress = {}
generated_pdfs = {}

class SearchRequest(BaseModel):
    topic: str

class MCQData(BaseModel):
    question: str
    options: List[str]
    answer: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: str
    total_links: Optional[int] = 0
    processed_links: Optional[int] = 0
    mcqs_found: Optional[int] = 0
    pdf_url: Optional[str] = None

def update_job_progress(job_id: str, status: str, progress: str, **kwargs):
    """Update job progress in memory"""
    if job_id not in job_progress:
        job_progress[job_id] = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "total_links": 0,
            "processed_links": 0,
            "mcqs_found": 0,
            "pdf_url": None
        }
    
    job_progress[job_id].update({
        "status": status,
        "progress": progress,
        **kwargs
    })

async def search_google_custom(topic: str) -> List[str]:
    """Search Google Custom Search API for ALL available Testbook links (paginated)"""
    query = f'{topic} Testbook [Solved] "This question was previously asked in" "BPSC CCE (Preliminary)" OR "BPSC Combined" OR "BPSC Prelims"'
    
    base_url = "https://www.googleapis.com/customsearch/v1"
    headers = {
        "Referer": "https://testbook.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    all_testbook_links = []
    start_index = 1
    max_results = 100  # Google Custom Search API limit
    
    try:
        while start_index <= max_results:
            params = {
                "key": GOOGLE_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "q": query,
                "num": 10,  # Maximum per request
                "start": start_index
            }
            
            print(f"Fetching results {start_index}-{start_index+9} for topic: {topic}")
            
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "items" not in data or len(data["items"]) == 0:
                print(f"No more results found after {start_index-1} results")
                break
            
            # Extract Testbook links from this batch
            batch_links = []
            for item in data["items"]:
                link = item.get("link", "")
                if "testbook.com" in link:
                    batch_links.append(link)
            
            all_testbook_links.extend(batch_links)
            print(f"Found {len(batch_links)} Testbook links in this batch. Total so far: {len(all_testbook_links)}")
            
            # Check if we got fewer than 10 results (last page)
            if len(data["items"]) < 10:
                print(f"Reached end of results with {len(data['items'])} items in last batch")
                break
            
            start_index += 10
            
            # Small delay to be respectful to the API
            await asyncio.sleep(0.5)
        
        print(f"Total Testbook links found: {len(all_testbook_links)}")
        return all_testbook_links
        
    except Exception as e:
        print(f"Error searching Google: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return []

async def scrape_mcq_content(url: str) -> Optional[MCQData]:
    """Scrape MCQ content from a Testbook page using playwright-stealth"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()
            
            # Apply stealth
            await stealth_async(page)
            
            # Navigate to page
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Extract question
            question_element = await page.query_selector('.questionBody')
            question = ""
            if question_element:
                question = await question_element.inner_text()
            
            # Extract options
            options = []
            option_elements = await page.query_selector_all('.options-list li')
            for option_elem in option_elements:
                option_text = await option_elem.inner_text()
                if option_text.strip():
                    options.append(option_text.strip())
            
            # Extract answer and solution
            answer = ""
            answer_element = await page.query_selector('.solution')
            if answer_element:
                answer = await answer_element.inner_text()
            
            await browser.close()
            
            # Return MCQ data if we found content
            if question and (options or answer):
                return MCQData(
                    question=question.strip(),
                    options=options,
                    answer=answer.strip()
                )
            
            return None
            
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def generate_pdf(mcqs: List[MCQData], topic: str, job_id: str) -> str:
    """Generate a professionally formatted PDF from MCQ data"""
    try:
        # Create PDFs directory if it doesn't exist
        pdf_dir = Path("/app/backend/pdfs")
        pdf_dir.mkdir(exist_ok=True)
        
        filename = f"Testbook_MCQs_{topic.replace(' ', '_')}_{job_id}.pdf"
        filepath = pdf_dir / filename
        
        # Create PDF document
        doc = SimpleDocTemplate(str(filepath), pagesize=A4, 
                              topMargin=1*inch, bottomMargin=1*inch,
                              leftMargin=1*inch, rightMargin=1*inch)
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        
        question_style = ParagraphStyle(
            'QuestionStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            leftIndent=0,
        )
        
        option_style = ParagraphStyle(
            'OptionStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=5,
            leftIndent=20,
        )
        
        answer_style = ParagraphStyle(
            'AnswerStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=20,
            leftIndent=0,
        )
        
        # Build PDF content
        story = []
        
        # Title page
        story.append(Paragraph(f"MCQs for: {topic}", title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Paragraph(f"Total Questions: {len(mcqs)}", styles['Normal']))
        story.append(PageBreak())
        
        # MCQ content
        for i, mcq in enumerate(mcqs, 1):
            # Question number and text
            story.append(Paragraph(f"<b>{i}. {mcq.question}</b>", question_style))
            
            # Options
            if mcq.options:
                for j, option in enumerate(mcq.options):
                    option_letter = chr(ord('A') + j)
                    story.append(Paragraph(f"{option_letter}. {option}", option_style))
            
            # Answer and solution
            if mcq.answer:
                story.append(Paragraph("<b>Answer & Solution:</b>", answer_style))
                story.append(Paragraph(mcq.answer, answer_style))
            
            # Add separator line
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("_" * 80, styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
        
        # Build PDF
        doc.build(story)
        
        return filename
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        raise

async def process_mcq_extraction(job_id: str, topic: str):
    """Background task to process MCQ extraction"""
    try:
        update_job_progress(job_id, "running", f"Searching for '{topic}'...")
        
        # Search for links
        links = await search_google_custom(topic)
        
        if not links:
            update_job_progress(job_id, "completed", f"No results found for '{topic}'. Please try another topic.", 
                              total_links=0, processed_links=0, mcqs_found=0)
            return
        
        update_job_progress(job_id, "running", f"Found {len(links)} links. Starting extraction...", 
                          total_links=len(links))
        
        # Extract MCQs from each link
        mcqs = []
        for i, link in enumerate(links, 1):
            update_job_progress(job_id, "running", f"Scraping result {i} of {len(links)}...", 
                              processed_links=i-1)
            
            mcq_data = await scrape_mcq_content(link)
            if mcq_data:
                mcqs.append(mcq_data)
                update_job_progress(job_id, "running", f"Scraping result {i} of {len(links)}...", 
                                  processed_links=i, mcqs_found=len(mcqs))
            else:
                update_job_progress(job_id, "running", f"Skipping result {i}: No MCQ found", 
                                  processed_links=i, mcqs_found=len(mcqs))
        
        if not mcqs:
            update_job_progress(job_id, "completed", f"No MCQs found for '{topic}'. Please try another topic.", 
                              total_links=len(links), processed_links=len(links), mcqs_found=0)
            return
        
        # Generate PDF
        update_job_progress(job_id, "running", "Generating PDF...", 
                          total_links=len(links), processed_links=len(links), mcqs_found=len(mcqs))
        
        pdf_filename = generate_pdf(mcqs, topic, job_id)
        pdf_url = f"/api/download/{pdf_filename}"
        
        # Store PDF info
        generated_pdfs[pdf_filename] = {
            "filename": pdf_filename,
            "topic": topic,
            "mcq_count": len(mcqs),
            "generated_at": datetime.now().isoformat()
        }
        
        update_job_progress(job_id, "completed", f"PDF generated successfully! Found {len(mcqs)} MCQs.", 
                          total_links=len(links), processed_links=len(links), 
                          mcqs_found=len(mcqs), pdf_url=pdf_url)
        
    except Exception as e:
        update_job_progress(job_id, "error", f"Error: {str(e)}")

@app.post("/api/generate-mcq-pdf", response_model=JobStatus)
async def generate_mcq_pdf(request: SearchRequest, background_tasks: BackgroundTasks):
    """Start MCQ extraction and PDF generation process"""
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    job_id = str(uuid.uuid4())
    
    # Initialize job progress
    update_job_progress(job_id, "starting", "Initializing...")
    
    # Start background task
    background_tasks.add_task(process_mcq_extraction, job_id, request.topic)
    
    return JobStatus(**job_progress[job_id])

@app.get("/api/job-status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a job"""
    if job_id not in job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(**job_progress[job_id])

@app.get("/api/download/{filename}")
async def download_pdf(filename: str):
    """Download generated PDF"""
    file_path = Path("/app/backend/pdfs") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/pdf'
    )

@app.get("/api/test-search/{topic}")
async def test_search(topic: str):
    """Test endpoint to verify Google Custom Search API"""
    try:
        links = await search_google_custom(topic)
        return {
            "topic": topic,
            "links_found": len(links),
            "links": links[:5]  # Return first 5 links for testing
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Testbook MCQ Scraper API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)