import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_student_registration_and_login_flow():
    """Test full registration, duplicate check, login, and profile retrieval flow."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dynamic unique roll number and email for idempotent test execution
        unique_suffix = uuid.uuid4().hex[:6].upper()
        roll_no = f"21ECA{unique_suffix}"
        email = f"student_{unique_suffix.lower()}@ecajmer.ac.in"

        reg_payload = {
            "college_roll_no": roll_no,
            "email": email,
            "full_name": "Test Student",
            "branch": "Computer Science and Engineering",
            "semester": 6,
            "degree": "B.Tech",
            "admission_year": 2021,
            "password": "Password123!",
        }

        # 1. Register student
        res = await client.post("/auth/register", json=reg_payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert "access_token" in data
        assert data["student"]["college_roll_no"] == roll_no
        assert data["student"]["email"] == email
        token = data["access_token"]

        # 2. Duplicate registration attempt with same roll number -> 409
        dup_res = await client.post("/auth/register", json=reg_payload)
        assert dup_res.status_code == 409

        # 3. Login with roll number
        login_res = await client.post(
            "/auth/login",
            json={"identifier": roll_no, "password": "Password123!"},
        )
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert "access_token" in login_data
        assert login_data["student"]["college_roll_no"] == roll_no

        # 4. Login with email
        login_email_res = await client.post(
            "/auth/login",
            json={"identifier": email, "password": "Password123!"},
        )
        assert login_email_res.status_code == 200

        # 5. Login with invalid password -> 401
        bad_login = await client.post(
            "/auth/login",
            json={"identifier": roll_no, "password": "WrongPassword!"},
        )
        assert bad_login.status_code == 401

        # 6. Retrieve profile with Bearer token
        me_res = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile["college_roll_no"] == roll_no
        assert profile["branch"] == "Computer Science and Engineering"
        assert profile["semester"] == 6

        # 7. Retrieve profile without token -> 401
        unauth_res = await client.get("/auth/me")
        assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_degree_and_semester_validation():
    """Test validation of programs: Masters limited to 4 semesters, B.Tech up to 8."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. MCA with semester 6 should be rejected with 400 Bad Request
        res_mca_bad = await client.post(
            "/auth/register",
            json={
                "college_roll_no": f"22MCA{uuid.uuid4().hex[:4].upper()}",
                "email": f"mca_{uuid.uuid4().hex[:4]}@ecajmer.ac.in",
                "full_name": "MCA Student",
                "branch": "Master of Computer Applications",
                "semester": 6,
                "degree": "MCA",
                "password": "Password123!",
            },
        )
        assert res_mca_bad.status_code == 400
        assert "4 semesters" in res_mca_bad.json()["detail"]

        # 2. MBA with semester 3 should succeed
        mca_roll = f"23MCA{uuid.uuid4().hex[:4].upper()}"
        res_mca_ok = await client.post(
            "/auth/register",
            json={
                "college_roll_no": mca_roll,
                "email": f"mca_{uuid.uuid4().hex[:4]}@ecajmer.ac.in",
                "full_name": "Valid MCA Student",
                "branch": "Master of Computer Applications",
                "semester": 3,
                "degree": "MCA",
                "password": "Password123!",
            },
        )
        assert res_mca_ok.status_code == 201
        assert res_mca_ok.json()["student"]["semester"] == 3

        # 3. B.Tech with semester 9 should be rejected with 422/400 (exceeds max 8 semesters)
        res_btech_bad = await client.post(
            "/auth/register",
            json={
                "college_roll_no": f"21ECA{uuid.uuid4().hex[:4].upper()}",
                "email": f"btech_{uuid.uuid4().hex[:4]}@ecajmer.ac.in",
                "full_name": "BTech Student",
                "branch": "Computer Science & Engineering",
                "semester": 9,
                "degree": "B.Tech",
                "password": "Password123!",
            },
        )
        assert res_btech_bad.status_code in (400, 422)

        # 4. Invalid roll number characters (special symbols) should be rejected
        res_invalid_roll = await client.post(
            "/auth/register",
            json={
                "college_roll_no": "21ECA$$$###",
                "email": f"stud_{uuid.uuid4().hex[:4]}@ecajmer.ac.in",
                "full_name": "Invalid Roll",
                "branch": "Civil Engineering",
                "semester": 4,
                "password": "Password123!",
            },
        )
        assert res_invalid_roll.status_code == 400
        assert "Roll number" in res_invalid_roll.json()["detail"]

        # 5. Invalid email should be rejected
        res_invalid_email = await client.post(
            "/auth/register",
            json={
                "college_roll_no": f"21ECA{uuid.uuid4().hex[:4].upper()}",
                "email": "not-an-email",
                "full_name": "Invalid Email",
                "branch": "Mechanical Engineering",
                "semester": 4,
                "password": "Password123!",
            },
        )
        assert res_invalid_email.status_code == 400
        assert "email" in res_invalid_email.json()["detail"].lower()
