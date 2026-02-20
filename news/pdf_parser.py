"""
PDF parsing service to extract content from daily newspaper PDFs.
"""
import logging
from PyPDF2 import PdfReader
from io import BytesIO

logger = logging.getLogger(__name__)


class PDFParserService:
    """Service to parse PDF files and extract article content."""
    
    @staticmethod
    def extract_text_from_pdf(pdf_file):
        """
        Extract all text content from a PDF file.
        
        Args:
            pdf_file: Django FileField object
            
        Returns:
            str: Extracted text content
        """
        try:
            # Read PDF file
            pdf_file.seek(0)
            pdf_reader = PdfReader(BytesIO(pdf_file.read()))
            
            text_content = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_num} ---\n{text}\n")
            
            return "\n".join(text_content)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    @staticmethod
    def parse_articles_from_pdf(pdf_file):
        """
        Parse PDF and extract article-like sections.
        
        Args:
            pdf_file: Django FileField object
            
        Returns:
            list: List of dictionaries containing article data
        """
        try:
            text_content = PDFParserService.extract_text_from_pdf(pdf_file)
            
            if not text_content:
                return []
            
            # Split by pages
            pages = text_content.split("--- Page")
            articles = []
            
            for page_content in pages:
                if not page_content.strip():
                    continue
                
                # Split by double newlines to find article sections
                sections = [s.strip() for s in page_content.split('\n\n') if s.strip()]
                
                for i, section in enumerate(sections):
                    if len(section) > 50:  # Only consider substantial text
                        lines = section.split('\n')
                        
                        # First line is likely the headline
                        title = lines[0].strip() if lines else "Untitled"
                        
                        # Rest is content
                        content = '\n'.join(lines[1:]) if len(lines) > 1 else section
                        
                        if len(title) > 10 and len(content) > 50:
                            articles.append({
                                'title': title[:200],  # Limit title length
                                'content': content[:1000],  # Limit content length
                                'description': content[:300],  # Short description
                            })
            
            return articles[:50]  # Limit to 50 articles
        except Exception as e:
            logger.error(f"Error parsing articles from PDF: {e}")
            return []
    
    @staticmethod
    def get_page_count(pdf_file):
        """
        Get total number of pages in PDF.
        
        Args:
            pdf_file: Django FileField object
            
        Returns:
            int: Number of pages
        """
        try:
            pdf_file.seek(0)
            pdf_reader = PdfReader(BytesIO(pdf_file.read()))
            return len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            return 0
