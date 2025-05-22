import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
import random
from codeforces_api import CodeforcesAPI
from db import get_db_connection

class ContestManager:
    def __init__(self):
        self.conn = get_db_connection()

    async def create_contest(self, name: str, duration: str, created_by: int, problem_count: int, min_rating: int, max_rating: int):
        """Create a new contest with randomly selected problems within a rating range"""
        # Fetch all problems from Codeforces API
        all_problems = await CodeforcesAPI.get_problem_tags()

        if not all_problems:
            print("Failed to fetch problems from Codeforces API.")
            return None

        # Filter problems by rating range
        filtered_problems = [problem for problem in all_problems 
                             if 'rating' in problem and min_rating <= problem['rating'] <= max_rating]

        if len(filtered_problems) < problem_count:
            print(f"Not enough problems found in the rating range {min_rating}-{max_rating}. Found: {len(filtered_problems)}")
            # handle this case by returning an error or adding fewer problems
            problem_count = len(filtered_problems) # Adjust problem_count to available problems
            if problem_count == 0:
                return None

        # Randomly select problems
        selected_problems = random.sample(filtered_problems, problem_count)

        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO contests (name, duration, created_by, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (name, duration, created_by, datetime.utcnow(), 'active')
        )
        self.conn.commit()
        contest_id = cursor.lastrowid

        if contest_id and selected_problems:
            await self.add_contest_problems(contest_id, selected_problems)

        return contest_id

    async def join_contest(self, contest_id: int, user_id: int):
        """Add a user to a contest"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'active':
            return False, "Contest is not active"
        cursor.execute("INSERT INTO contest_participants (contest_id, discord_id) VALUES (?, ?)", (contest_id, user_id))
        self.conn.commit()
        return True, "Successfully joined the contest"

    async def start_contest(self, contest_id: int):
        """Start a contest"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status, duration FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'active':
            return False, "Contest is not active"
        start_time = datetime.utcnow()
        duration = self._parse_duration(contest['duration'])
        end_time = start_time + duration
        cursor.execute("UPDATE contests SET status = ?, start_time = ?, end_time = ? WHERE id = ?", ('running', start_time, end_time, contest_id))
        self.conn.commit()
        return True, "Contest started successfully"

    async def end_contest(self, contest_id: int):
        """End a contest and calculate results"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'running':
            return False, "Contest is not running"
        cursor.execute("SELECT discord_id FROM contest_participants WHERE contest_id = ?", (contest_id,))
        participants = cursor.fetchall()
        results = []
        for participant in participants:
            user_id = participant['discord_id']
            cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                continue
            submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
            if not submissions:
                continue
            score = self._calculate_contest_score(submissions, contest['start_time'], contest['end_time'], contest['problems'])
            results.append({'user_id': user_id, 'handle': user['cf_handle'], 'score': score})
        results.sort(key=lambda x: x['score'], reverse=True)
        cursor.execute("UPDATE contests SET status = ? WHERE id = ?", ('ended', contest_id))
        self.conn.commit()
        return True, "Contest ended successfully"

    def _parse_duration(self, duration: str) -> timedelta:
        """Parse duration string into timedelta"""
        value = int(duration[:-1])
        unit = duration[-1].lower()
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'd':
            return timedelta(days=value)
        else:
            return timedelta(hours=1)

    def _calculate_contest_score(self, submissions, start_time, end_time, problems):
        """Calculate user's score for the contest"""
        score = 0
        solved_problems = set()
        for submission in submissions:
            submission_time = datetime.fromtimestamp(submission["creationTimeSeconds"])
            if not (start_time <= submission_time <= end_time):
                continue
            problem_id = f"{submission['problem']['contestId']}{submission['problem']['index']}"
            if problem_id not in solved_problems and submission["verdict"] == "OK":
                solved_problems.add(problem_id)
                if "rating" in submission["problem"]:
                    score += submission["problem"]["rating"] // 100
        return score

    async def get_contest_status(self, contest_id: int):
        """Get detailed status of a contest"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, u.cf_handle 
            FROM contests c 
            LEFT JOIN users u ON c.created_by = u.discord_id 
            WHERE c.id = ?
        """, (contest_id,))
        contest = cursor.fetchone()

        if not contest:
            return False, "Contest not found"

        # Get participants
        cursor.execute("""
            SELECT cp.discord_id, cp.score, u.cf_handle 
            FROM contest_participants cp 
            LEFT JOIN users u ON cp.discord_id = u.discord_id 
            WHERE cp.contest_id = ?
            ORDER BY cp.score DESC
        """, (contest_id,))
        participants = cursor.fetchall()

        return True, {
            'id': contest['id'],
            'name': contest['name'],
            'status': contest['status'],
            'duration': contest['duration'],
            'created_by': contest['cf_handle'],
            'created_at': contest['created_at'],
            'start_time': datetime.fromisoformat(contest['start_time']) if contest['start_time'] else None,
            'end_time': datetime.fromisoformat(contest['end_time']) if contest['end_time'] else None,
            'participants': [{
                'handle': p['cf_handle'],
                'score': p['score']
            } for p in participants]
        }

    async def list_contests(self):
        """List all active contests"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, u.cf_handle 
            FROM contests c 
            LEFT JOIN users u ON c.created_by = u.discord_id 
            WHERE c.status IN ('active', 'running')
            ORDER BY c.created_at DESC
        """)
        contests = cursor.fetchall()

        if not contests:
            return False, "No active contests found"

        result = []
        for contest in contests:
            # Get participant count
            cursor.execute(
                "SELECT COUNT(*) as count FROM contest_participants WHERE contest_id = ?",
                (contest['id'],)
            )
            participant_count = cursor.fetchone()['count']

            result.append({
                'id': contest['id'],
                'name': contest['name'],
                'status': contest['status'],
                'duration': contest['duration'],
                'created_by': contest['cf_handle'],
                'created_at': contest['created_at'],
                'start_time': contest['start_time'],
                'end_time': contest['end_time'],
                'participants': participant_count
            })

        return True, result

    async def add_contest_problems(self, contest_id: int, problems: List[Dict]):
        """Add problems to a contest"""
        cursor = self.conn.cursor()
        for problem in problems:
            cursor.execute("""
                INSERT INTO contest_problems 
                (contest_id, problem_id, problem_name, problem_rating, problem_tags)
                VALUES (?, ?, ?, ?, ?)
            """, (
                contest_id,
                f"{problem['contestId']}{problem['index']}",
                problem['name'],
                problem.get('rating'),
                ','.join(problem.get('tags', []))
            ))
        self.conn.commit()
        return True, f"Added {len(problems)} problems to contest"

    async def get_contest_problems(self, contest_id: int):
        """Get all problems for a contest"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT problem_id, problem_name, problem_rating, problem_tags
            FROM contest_problems
            WHERE contest_id = ?
            ORDER BY problem_rating
        """, (contest_id,))
        problems = cursor.fetchall()

        if not problems:
            return False, "No problems found for this contest"

        return True, [{
            'id': p['problem_id'],
            'name': p['problem_name'],
            'rating': p['problem_rating'],
            'tags': p['problem_tags'].split(',') if p['problem_tags'] else []
        } for p in problems]

    async def track_submission(self, contest_id: int, user_id: int, submission: Dict):
        """Track a user's submission in a contest"""
        cursor = self.conn.cursor()
        problem_id = f"{submission['problem']['contestId']}{submission['problem']['index']}"

        cursor.execute("""
            INSERT OR IGNORE INTO contest_submissions
            (contest_id, discord_id, problem_id, submission_id, submission_time, verdict)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            contest_id,
            user_id,
            problem_id,
            submission['id'],
            datetime.fromtimestamp(submission['creationTimeSeconds']),
            submission['verdict']
        ))
        self.conn.commit()

    async def check_problem_status(self, contest_id: int, user_id: int):
        """Check which problems a user has solved in a contest"""
        cursor = self.conn.cursor()

        # Get all problems in the contest
        cursor.execute("""
            SELECT problem_id, problem_name, problem_rating
            FROM contest_problems
            WHERE contest_id = ?
        """, (contest_id,))
        problems = cursor.fetchall()

        # Get user's submissions
        cursor.execute("""
            SELECT problem_id, verdict
            FROM contest_submissions
            WHERE contest_id = ? AND discord_id = ?
            ORDER BY submission_time DESC
        """, (contest_id, user_id))
        submissions = cursor.fetchall()

        # Track solved problems
        solved_problems = set()
        for submission in submissions:
            if submission['verdict'] == 'OK':
                solved_problems.add(submission['problem_id'])

        # Create result with problem status
        result = []
        for problem in problems:
            result.append({
                'id': problem['problem_id'],
                'name': problem['problem_name'],
                'rating': problem['problem_rating'],
                'solved': problem['problem_id'] in solved_problems
            })

        return True, result

    async def update_contest_scores(self, contest_id: int):
        """Update scores for all participants in a contest"""
        cursor = self.conn.cursor()

        # Get all participants
        cursor.execute("""
            SELECT discord_id
            FROM contest_participants
            WHERE contest_id = ?
        """, (contest_id,))
        participants = cursor.fetchall()

        for participant in participants:
            # Get user's solved problems
            success, problems = await self.check_problem_status(contest_id, participant['discord_id'])
            if not success:
                continue

            # Calculate score based on solved problems
            score = sum(problem['rating'] // 100 for problem in problems if problem['solved'])

            # Update score
            cursor.execute("""
                UPDATE contest_participants
                SET score = ?
                WHERE contest_id = ? AND discord_id = ?
            """, (score, contest_id, participant['discord_id']))

        self.conn.commit()
        return True, "Scores updated successfully" 