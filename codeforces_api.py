import aiohttp
import asyncio
from datetime import datetime, timedelta

class CodeforcesAPI:
    BASE_URL = "https://codeforces.com/api"
    
    @staticmethod
    async def get_user_submissions(handle: str, count: int = 1000):
        """Get user's recent submissions"""
        async with aiohttp.ClientSession() as session:
            url = f"{CodeforcesAPI.BASE_URL}/user.status"
            params = {
                "handle": handle,
                "count": count
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["status"] == "OK":
                        return data["result"]
                return None
    
    @staticmethod
    async def get_user_info(handle: str):
        """Get user's information"""
        async with aiohttp.ClientSession() as session:
            url = f"{CodeforcesAPI.BASE_URL}/user.info"
            params = {"handles": handle}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["status"] == "OK":
                        return data["result"][0]
                return None
    
    @staticmethod
    async def get_problem_tags():
        """Get all problem tags"""
        async with aiohttp.ClientSession() as session:
            url = f"{CodeforcesAPI.BASE_URL}/problemset.problems"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["status"] == "OK":
                        return data["result"]["problems"]
                return None
    
    @staticmethod
    def calculate_daily_progress(submissions, date):
        """Calculate problems solved on a specific date"""
        solved_problems = set()
        for submission in submissions:
            submission_time = datetime.fromtimestamp(submission["creationTimeSeconds"])
            if (submission_time.date() == date and 
                submission["verdict"] == "OK" and 
                "contestId" in submission["problem"]):
                problem_id = f"{submission['problem']['contestId']}{submission['problem']['index']}"
                solved_problems.add(problem_id)
        return len(solved_problems)
    
    @staticmethod
    def get_user_statistics(submissions):
        """Calculate user statistics from submissions"""
        stats = {
            "total_solved": 0,
            "problems_by_rating": {},
            "problems_by_tag": {},
            "solved_problems": set()
        }
        
        for submission in submissions:
            if submission["verdict"] == "OK":
                problem = submission["problem"]
                problem_id = f"{problem['contestId']}{problem['index']}"
                
                if problem_id not in stats["solved_problems"]:
                    stats["solved_problems"].add(problem_id)
                    stats["total_solved"] += 1
                    
                    # Count by rating
                    if "rating" in problem:
                        rating = problem["rating"]
                        stats["problems_by_rating"][rating] = stats["problems_by_rating"].get(rating, 0) + 1
                    
                    # Count by tags
                    for tag in problem["tags"]:
                        stats["problems_by_tag"][tag] = stats["problems_by_tag"].get(tag, 0) + 1
        
        return stats 