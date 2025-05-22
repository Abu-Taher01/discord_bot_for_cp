import aiohttp
import asyncio
from datetime import datetime, timedelta

class CodeforcesAPI:
    BASE_URL = "https://codeforces.com/api"

    @staticmethod
    async def get_user_submissions(handle: str):
        """Get all of user's submissions using pagination"""
        all_submissions = []
        from_entry = 1
        count = 1000  # Fetch 1000 submissions at a time

        async with aiohttp.ClientSession() as session:
            while True:
                url = f"{CodeforcesAPI.BASE_URL}/user.status"
                params = {
                    "handle": handle,
                    "from": from_entry,
                    "count": count
                }

                try:
                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            print(f"Error fetching submissions for {handle}: {response.status}")
                            break

                        data = await response.json()

                        if data["status"] != "OK":
                            print(f"Codeforces API error for {handle}: {data['comment']}")
                            break

                        submissions = data["result"]

                        if not submissions:
                            # No more submissions
                            break

                        all_submissions.extend(submissions)

                        # If the number of submissions returned is less than the requested count,
                        # it means we have fetched all available submissions.
                        if len(submissions) < count:
                            break

                        from_entry += count  # Move to the next batch
                except Exception as e:
                    print(f"Error fetching submissions for {handle}: {str(e)}")
                    break

        return all_submissions

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