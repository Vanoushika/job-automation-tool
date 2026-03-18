import requests
from datetime import datetime
import re
import json

class SimplifyJobsScraper:
    def __init__(self):
        self.base_url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
    
    def fetch_jobs(self):
        print("🔍 Fetching jobs from SimplifyJobs...")
        
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
            
            content = response.text
            jobs = self._parse_markdown_table(content)
            
            print(f"✅ Found {len(jobs)} total jobs!")
            return jobs
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def _parse_markdown_table(self, content):
        jobs = []
        lines = content.split('\n')
        
        for line in lines:
            if '---' in line or 'Company' in line or 'Role' in line:
                continue
            
            if line.count('|') >= 4 and line.strip().startswith('|'):
                job = self._parse_job_row(line)
                if job:
                    jobs.append(job)
        
        return jobs
    
    def _parse_job_row(self, row):
        try:
            parts = [p.strip() for p in row.split('|')]
            parts = [p for p in parts if p]
            
            if len(parts) < 4:
                return None
            
            company = parts[0]
            role = parts[1]
            location = parts[2]
            
            url_match = re.search(r'\[.*?\]\((https?://[^\)]+)\)', parts[3])
            apply_url = url_match.group(1) if url_match else None
            
            age = parts[4] if len(parts) > 4 else "Unknown"
            
            if not apply_url:
                return None
            
            return {
                'company': company,
                'role': role,
                'location': location,
                'apply_url': apply_url,
                'age': age,
                'scraped_at': datetime.now().isoformat(),
                'source': 'SimplifyJobs'
            }
        except Exception as e:
            return None
    
    def filter_recent_jobs(self, jobs, max_days=3):
        filtered = []
        
        for job in jobs:
            age = job.get('age', '')
            
            if 'd' in age.lower():
                try:
                    match = re.search(r'(\d+)d', age.lower())
                    if match:
                        days = int(match.group(1))
                        if days <= max_days:
                            filtered.append(job)
                except:
                    pass
            elif age == "Unknown" or '0d' in age:
                filtered.append(job)
        
        print(f"📅 Filtered to {len(filtered)} jobs posted in last {max_days} days")
        return filtered
    
    def filter_by_keywords(self, jobs, keywords):
        filtered = []
        keywords_lower = [k.lower() for k in keywords]
        
        for job in jobs:
            role_lower = job['role'].lower()
            if any(keyword in role_lower for keyword in keywords_lower):
                filtered.append(job)
        
        print(f"🔍 Found {len(filtered)} jobs matching keywords: {keywords}")
        return filtered


if __name__ == "__main__":
    scraper = SimplifyJobsScraper()
    
    all_jobs = scraper.fetch_jobs()
    
    keywords = ['software engineer', 'backend', 'full stack', 'full-stack']
    matching_jobs = scraper.filter_by_keywords(all_jobs, keywords)
    
    recent_jobs = scraper.filter_recent_jobs(matching_jobs, max_days=7)
    
    print(f"\n🎯 TOP 15 RECENT MATCHES:")
    print("=" * 80)
    
    for i, job in enumerate(recent_jobs[:15], 1):
        print(f"\n{i}. {job['company']}")
        print(f"   Role: {job['role']}")
        print(f"   📍 {job['location']}")
        print(f"   📅 Posted: {job['age']} ago")
        print(f"   🔗 {job['apply_url']}")
    
    with open('jobs_output.json', 'w') as f:
        json.dump(recent_jobs, f, indent=2)
    
    print(f"\n✅ Saved {len(recent_jobs)} jobs to jobs_output.json")
