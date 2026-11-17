"""Fill the database with realistic demo data so the app looks alive.

Run:  python -m scripts.seed          (inside backend/, or `docker compose exec backend python -m scripts.seed`)

Logins created (password for all: demo1234):
  demo@coep.ac.in     student with a room, roommate, expenses, chores, complaints
  warden@sunrise.in   warden of "sunrise-pg" (complaints dashboard, rulebook, ML training)
"""
import asyncio
import random
from datetime import timedelta

from app.ai import features
from app.db import create_indexes, get_db
from app.security import hash_password, is_student_email
from app.services import learner, matching, rag, splitting
from app.utils import now

rnd = random.Random(42)
FEMALE = ["Priya", "Ananya", "Sneha", "Kavya", "Isha", "Riya", "Pooja", "Neha", "Diya", "Aditi", "Meera", "Tanvi", "Shruti", "Nikita", "Aarohi"]
MALE = ["Rahul", "Arjun", "Rohan", "Karan", "Aditya", "Vikram", "Siddharth", "Aman", "Yash", "Kunal", "Harsh", "Nikhil", "Varun", "Ishaan", "Dev"]
SURNAMES = ["Sharma", "Patil", "Rao", "Iyer", "Gupta", "Kulkarni", "Reddy", "Nair", "Joshi", "Deshmukh", "Singh", "Mehta"]
AREAS = {"Pune": ["Kothrud", "Viman Nagar", "Hinjewadi", "Baner", "Shivajinagar"], "Bengaluru": ["Koramangala", "HSR Layout", "Indiranagar", "Electronic City"]}
COLLEGES = ["COEP", "PICT", "MIT-WPU", "Symbiosis", "Infosys", "TCS", "Wipro", "Christ University"]
BIOS = [
    "Final year CSE student. Into coding, DSA and cricket on weekends. Quiet person, I study late at night.",
    "Working at a startup, love cooking and trekking. Pretty social, enjoy movies with friends.",
    "MBA student, early riser, gym every morning. Like a clean and calm room.",
    "Software engineer, gamer (Valorant, BGMI) and anime fan. Night owl but use headphones.",
    "Design student who loves music, guitar and painting. Friendly, a little messy honestly.",
    "Preparing for placements, reading and badminton. Introvert, need silence to study.",
    "Data analyst, foodie and traveller. Love chai and long talks, but respect quiet hours.",
    "Mechanical engineering student, football and gym. Outgoing, friends visit sometimes.",
]
TIMES_SLEEP = ["22:30", "23:00", "23:30", "00:00", "00:30", "01:00", "01:30", "02:00"]
TIMES_WAKE = ["05:30", "06:00", "06:30", "07:00", "07:30", "08:00", "08:30", "09:00"]

RULEBOOK = """Sunrise PG Rules and Guidelines

1. The main gate closes at 10:30 PM on weekdays and 11:30 PM on Friday and Saturday. Late entry needs prior permission from the warden.

2. Visitors are allowed only in the common room between 5 PM and 8 PM. Overnight guests are not allowed.

3. Breakfast is served 7:30-9:30 AM, lunch 12:30-2:30 PM and dinner 8:00-10:00 PM. Tell the mess a day before if you will skip meals.

4. Rent is due by the 5th of every month. A late fee of Rs 100 per day applies after that.

5. Induction stoves, heaters and irons above 1000W are not allowed in rooms. Use the common pantry.

6. Wi-Fi password changes on the 1st of every month and is shared on the notice board.

7. Smoking and alcohol are strictly prohibited inside the PG premises. First offence is a warning, second is a Rs 2000 fine.

8. Laundry is collected every Tuesday and Friday at 9 AM from the ground floor.

9. To vacate, give one month notice. The security deposit is refunded within 15 days after room inspection.

10. For maintenance issues, raise a complaint in the Hostel/PG Life app. Urgent issues: call the warden at the front desk."""


def answers() -> dict:
    return {
        "sleep_time": rnd.choice(TIMES_SLEEP), "wake_time": rnd.choice(TIMES_WAKE), "cleanliness": rnd.randint(2, 5),
        "study_style": rnd.choice(["silent", "silent", "music", "library"]), "food": rnd.choice(["veg", "veg", "nonveg", "eggetarian", "flexible"]),
        "smoking": rnd.random() < 0.15, "drinking": rnd.random() < 0.3, "guests": rnd.randint(0, 3), "noise": rnd.randint(1, 5),
        "ac": rnd.choice(["ac", "fan", "either"]), "personality": rnd.choice(["introvert", "ambivert", "extrovert"]),
    }


async def add_user(db, name, email, gender, city, hostel="sunrise-pg", role="student", ans=None, bio=None):
    res = await db.users.insert_one({"name": name, "email": email, "password_hash": hash_password("demo1234"), "role": role,
                                     "hostel": hostel, "verified": is_student_email(email), "email_verified": True, "auth_provider": "password", "blocked": [], "created_at": now()})
    uid = res.inserted_id
    if role == "student":
        low = rnd.choice([5000, 6000, 7000, 8000])
        prof = {"user_id": uid, "city": city, "city_key": city.lower(), "area": rnd.choice(AREAS[city]), "gender": gender, "gender_pref": "same",
                "budget_min": low, "budget_max": low + rnd.choice([2000, 3000, 4000]), "move_in": (now() + timedelta(days=rnd.randint(0, 25))).date().isoformat(),
                "room_type": "2-sharing", "college_or_office": rnd.choice(COLLEGES), "bio": bio or rnd.choice(BIOS),
                "interests": [], "answers": ans or answers(), "dealbreakers": ["smoking"] if rnd.random() < 0.3 else [], "updated_at": now()}
        prof.update(await features.embeddings_for(features.profile_text(prof), str(uid)))
        await db.profiles.insert_one(prof)
    return uid


async def main():
    db = get_db()
    for name in await db.list_collection_names():
        await db[name].drop()
    await create_indexes()

    demo_ans = {"sleep_time": "01:00", "wake_time": "08:00", "cleanliness": 4, "study_style": "silent", "food": "veg", "smoking": False,
                "drinking": False, "guests": 1, "noise": 2, "ac": "fan", "personality": "introvert"}
    demo = await add_user(db, "Priya Sharma", "demo@coep.ac.in", "female", "Pune", ans=demo_ans, bio=BIOS[0])
    roomie = await add_user(db, "Ananya Rao", "ananya@demo.in", "female", "Pune", ans={**demo_ans, "sleep_time": "00:30", "ac": "either"}, bio=BIOS[5])
    warden = await add_user(db, "Mr. Mehta (Warden)", "warden@sunrise.in", "male", "Pune", role="warden")

    people = [demo, roomie]
    for i in range(36):
        gender = "female" if i % 2 == 0 else "male"
        first = (FEMALE if gender == "female" else MALE)[i // 2 % 15]
        city = "Pune" if i < 26 else "Bengaluru"
        people.append(await add_user(db, f"{first} {rnd.choice(SURNAMES)}", f"{first.lower()}{i}@{'pict.edu.in' if i % 3 == 0 else 'gmail.com'}", gender, city))

    # Accepted request + room for the demo user
    req = await db.match_requests.insert_one({"from_user": demo, "to_user": roomie, "message": "Hi! Looks like we have similar habits.", "status": "accepted", "created_at": now() - timedelta(days=20)})
    await db.messages.insert_many([
        {"request_id": req.inserted_id, "sender": demo, "text": "Hi Ananya! Want to share a room at Sunrise PG?", "created_at": now() - timedelta(days=20), "flagged": False, "warning": ""},
        {"request_id": req.inserted_id, "sender": roomie, "text": "Yes! I also sleep late and like a quiet room.", "created_at": now() - timedelta(days=20, minutes=-5), "flagged": False, "warning": ""},
    ])
    # A pending incoming request for the demo user
    others = [p async for p in db.profiles.find({"city_key": "pune", "gender": "female", "user_id": {"$nin": [demo, roomie]}})]
    if others:
        await db.match_requests.insert_one({"from_user": others[0]["user_id"], "to_user": demo, "message": "Hey, are you still looking?", "status": "pending", "created_at": now()})

    room = await db.rooms.insert_one({"name": "Room 204, Sunrise PG", "members": [demo, roomie], "agreement": None, "created_at": now() - timedelta(days=18)})
    members = [str(demo), str(roomie)]
    for title, amount, cat, payer, days in [("Rent - November", 16000, "rent", demo, 15), ("Electricity bill", 1340, "electricity", roomie, 10),
                                            ("Wi-Fi (Airtel)", 799, "wifi", demo, 9), ("Groceries - DMart", 1260, "groceries", roomie, 4), ("Maid", 1500, "maid", demo, 2)]:
        await db.expenses.insert_one({"room_id": room.inserted_id, "title": title, "amount": amount, "category": cat, "paid_by": payer,
                                      "shares": splitting.shares_for(amount, members), "added_by": payer, "created_at": now() - timedelta(days=days)})
    for i, task in enumerate(["Clean bathroom", "Take out trash", "Refill water can", "Sweep the room"]):
        await db.chores.insert_one({"room_id": room.inserted_id, "task": task, "every_days": 7, "assigned_to": [demo, roomie][i % 2], "done_count": rnd.randint(0, 3), "last_done": None, "created_at": now()})

    # Complaints (one is old and unresolved -> escalated)
    for title, desc, days, status in [("Ceiling fan not working", "Fan in room 204 makes noise and stops, switch sparks sometimes", 3, "open"),
                                      ("Wi-Fi very slow at night", "Internet drops after 11 PM on 2nd floor", 1, "in_progress"),
                                      ("Bathroom tap leaking", "Tap leaking continuously, water wasted", 6, "resolved")]:
        ai = await features.classify_complaint(f"{title}. {desc}", None, str(demo))
        created = now() - timedelta(days=days)
        await db.complaints.insert_one({"raised_by": demo, "raiser_name": "Priya Sharma", "hostel": "sunrise-pg", "title": title, "description": desc, "room_no": "204",
                                        "photo_url": None, "category": ai["category"], "priority": ai["priority"], "ai_summary": ai["summary"], "ai_source": ai["source"],
                                        "status": status, "notes": [], "rating": 4 if status == "resolved" else None, "created_at": created,
                                        "resolved_at": created + timedelta(hours=20) if status == "resolved" else None})

    # Marketplace
    for title, price, cat, cond, seller in [("Symphony air cooler", 2200, "appliances", "good", people[4]), ("Engineering Mathematics (B.S. Grewal)", 300, "books", "good", people[5]),
                                            ("Hero Sprint cycle with lock", 3500, "cycles", "like new", people[6]), ("Study table + chair", 1200, "furniture", "fair", people[7]),
                                            ("Electric kettle 1.5L", 450, "appliances", "like new", roomie), ("Casio scientific calculator", 600, "electronics", "good", people[8])]:
        u = await db.users.find_one({"_id": seller})
        await db.listings.insert_one({"seller": seller, "seller_name": u["name"], "seller_verified": u["verified"], "title": title, "description": f"{cond.capitalize()} condition, pick up from hostel.",
                                      "price": price, "category": cat, "condition": cond, "location": "Sunrise PG, Kothrud", "photo_url": None, "status": "available", "flag_reason": "", "created_at": now()})

    await rag.ingest("sunrise-pg", "Sunrise PG Rulebook", RULEBOOK, str(warden))

    # Synthetic 1-month ratings so the learning matcher has data (in real life these come from users)
    profs = [p async for p in db.profiles.find({})]
    for _ in range(60):
        a, b = rnd.sample(profs, 2)
        s = matching.factor_scores(a["answers"], b["answers"])
        happiness = 0.45 * s["sleep_time"] + 0.25 * s["cleanliness"] + 0.15 * s["guests"] + 0.15 * s["noise"] + rnd.uniform(-0.15, 0.15)
        await db.ratings.insert_one({"from_user": a["user_id"], "to_user": b["user_id"], "stars": 5 if happiness > 0.7 else 4 if happiness > 0.55 else 2, "created_at": now()})
    result = await learner.train()

    print(f"Seeded {len(people)} students, 1 warden, 1 room, 6 listings, 3 complaints, rulebook.")
    print("Learning matcher:", {k: result.get(k) for k in ("trained", "learned_auc", "default_auc", "active")})
    print("Login: demo@coep.ac.in / demo1234   |   warden@sunrise.in / demo1234")


if __name__ == "__main__":
    asyncio.run(main())
