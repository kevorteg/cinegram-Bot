from guessit import guessit
import logging

logger = logging.getLogger(__name__)

class FilenameParser:
    
    @staticmethod
    def parse_filename(filename: str):
        """
        Parses a messy filename and returns a clean dictionary with title and year.
        Example: 'Night.of.the.Living.Dead.1968.720p.mkv' -> {'title': 'Night of the Living Dead', 'year': '1968'}
        """
        try:
            # Pre-cleaning: Remove explicit spam before Guessit
            import re
            
            # 1. Remove @usernames (e.g. @cesser16)
            clean_name = re.sub(r'@\w+', '', filename)
            
            # 2. Remove URLs
            clean_name = re.sub(r'https?://\S+|www\.\S+', '', clean_name)
            
            # 3. Remove other common spam if needed
            clean_name = clean_name.replace('_', ' ') # Replace underscores
            
            # Guessit magic on cleaned name
            data = guessit(clean_name)
            
            title = data.get('title')
            year = data.get('year')
            
            # Basic Validation
            if not title:
                return None
                
            return {
                "title": title,
                "year": str(year) if year else None
            }
            
        except Exception as e:
            logger.error(f"Error parsing filename {filename}: {e}")
            return None
